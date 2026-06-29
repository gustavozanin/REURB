# -*- coding: utf-8 -*-

import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path

import arcpy

from caminhos_gerais import projeto_arcgis
from responsaveis_tecnicos import resolver_responsavel


STATUS_LEGENDA = {
    0: ("Sem status", [230, 230, 230, 100]),
    1: ("Concluida no ponto fixo", [46, 125, 50, 100]),
    2: ("Em andamento", [249, 168, 37, 100]),
    3: ("Aguardando inicio", [144, 202, 249, 100]),
    4: ("Concluida em campo", [102, 187, 106, 100]),
    5: ("Litigio", [142, 36, 170, 100]),
    6: ("Pendente de confirmacao", [255, 183, 77, 100]),
    7: ("Area Rural", [156, 204, 101, 100]),
    8: ("Cancelado", [239, 83, 80, 100]),
    9: ("Terreno", [189, 189, 189, 100]),
    10: ("Faixa de Dominio", [144, 164, 174, 100]),
    11: ("Alagado", [79, 195, 247, 100]),
}

WORLD_IMAGERY_URL = r"https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer"
SIMBOLOGIA_PERIMETRO_OVERVIEW = Path(__file__).parent / "layers" / "PERIMETRO_OVERVIEW.lyrx"
FATOR_ZOOM_PLANTA_SITUACAO = 3.5


def slug_resultado(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto or "bairro"


def pasta_resultados(numero_reurb_coletivo, bairro):
    nome_base = numero_reurb_coletivo.replace("/", "_")
    pasta = Path(__file__).parent / "resultados" / f"{slug_resultado(bairro)}_{nome_base}"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def decimal_texto(valor, casas=4):
    if valor in (None, ""):
        return ""
    return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def resolver_shp_bairro(numero_reurb_coletivo, bairro, shp_bairro=None):
    if shp_bairro and arcpy.Exists(shp_bairro):
        return shp_bairro

    pasta_shp = Path(r"C:\REURB\SHP")
    numero_limpo = numero_reurb_coletivo.replace("/", "_")
    bairro_slug = slug_resultado(bairro)
    candidatos = [
        pasta_shp / f"bairro_{bairro_slug}_{numero_limpo}.shp",
        pasta_shp / f"bairro_{bairro_slug}_{numero_limpo.replace('0506', '0526', 1)}.shp",
        pasta_shp / f"bairro_{bairro_slug}_{numero_limpo.replace('0526', '0506', 1)}.shp",
    ]
    for candidato in candidatos:
        if arcpy.Exists(str(candidato)):
            return str(candidato)

    encontrados = sorted(pasta_shp.glob(f"bairro_{bairro_slug}_*.shp"))
    if encontrados:
        return str(encontrados[0])
    return None


def resolver_raster_situacao(bairro, raster_situacao=None):
    if raster_situacao and arcpy.Exists(raster_situacao):
        return raster_situacao

    bairro_slug = slug_resultado(bairro)
    candidatos_por_bairro = {
        "centro": [
            Path(r"C:\Users\gusta\Downloads\SHPS_Rec\Centro_PeriMirim_Rec.tif"),
            Path(r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\MyProject15\CENTRO_CAMPODEPOUSO_Clip1.tif"),
        ],
        "campo_de_pouso": [
            Path(r"C:\Users\gusta\Downloads\SHPS_Rec\CampodePouso_Rec_TIFF.tif"),
            Path(r"C:\Users\gusta\Downloads\CENTRO_CAMPO DE POUSO.tif"),
            Path(r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\MyProject15\CENTRO_CAMPODEPOUSO_Clip1.tif"),
        ],
    }
    for candidato in candidatos_por_bairro.get(bairro_slug, []):
        if arcpy.Exists(str(candidato)):
            return str(candidato)

    pastas = [
        Path(r"C:\Users\gusta\Downloads\SHPS_Rec"),
        Path(r"C:\Users\gusta\Downloads"),
        Path(r"C:\REURB\SHP"),
    ]
    termos = [termo for termo in bairro_slug.split("_") if termo]
    for pasta in pastas:
        if not pasta.exists():
            continue
        for raster in list(pasta.glob("*.tif")) + list(pasta.glob("*.tiff")):
            nome = slug_resultado(raster.stem)
            if termos and all(termo in nome for termo in termos):
                return str(raster)
    return None


def _campo_existente(dataset, candidatos):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(dataset)}
    for candidato in candidatos:
        if candidato.lower() in campos:
            return campos[candidato.lower()]
    return None


def _where_status(campo_status, status):
    delimitado = arcpy.AddFieldDelimiters(arcpy.env.workspace or "", campo_status)
    return f"{delimitado} = {int(status)}"


def _limpar_mapa(aprx_map):
    for layer in list(aprx_map.listLayers()):
        try:
            aprx_map.removeLayer(layer)
        except Exception:
            pass
    for tabela in list(aprx_map.listTables()):
        try:
            aprx_map.removeTable(tabela)
        except Exception:
            pass


def _remover_camadas_por_nome(aprx, nomes):
    nomes_normalizados = {str(nome).strip().lower() for nome in nomes}
    for mapa in aprx.listMaps():
        for layer in list(mapa.listLayers()):
            try:
                if str(layer.name).strip().lower() in nomes_normalizados:
                    mapa.removeLayer(layer)
            except Exception:
                pass


def _campo_tipo(dataset, campo):
    for field in arcpy.ListFields(dataset):
        if field.name.lower() == str(campo).lower():
            return field.type
    return ""


def _valor_sql(valor, tipo_campo):
    if valor is None:
        return "NULL"
    if tipo_campo in ("Integer", "SmallInteger", "Single", "Double", "OID"):
        try:
            return str(int(valor))
        except Exception:
            try:
                return str(float(valor))
            except Exception:
                pass
    return "'" + str(valor).replace("'", "''") + "'"


def _clausula_igual(dataset, campo, valor):
    delimitado = arcpy.AddFieldDelimiters("", campo)
    return f"{delimitado} = {_valor_sql(valor, _campo_tipo(dataset, campo))}"


def _clausula_igual_ci(dataset, campo, valor):
    delimitado = arcpy.AddFieldDelimiters("", campo)
    return f"UPPER({delimitado}) = UPPER({_valor_sql(valor, 'String')})"


def _variantes_processo_coletivo(numero):
    texto = str(numero or "").strip()
    if not texto:
        return []
    variantes = {texto, texto.replace("/", "_"), texto.replace("_", "/")}
    return [item for item in variantes if item]


def _montar_filtros_atributo(dataset, pares):
    filtros = []
    vistos = set()
    for candidatos, valor in pares:
        if valor in (None, ""):
            continue
        campo = _campo_existente(dataset, candidatos)
        if not campo:
            continue
        for candidato in _variantes_processo_coletivo(valor) if any(
            nome in ("n_coletivo", "coletivo", "reurb") for nome in candidatos
        ) else [valor]:
            for clausula in (
                _clausula_igual(dataset, campo, candidato),
                _clausula_igual_ci(dataset, campo, candidato),
            ):
                if clausula and clausula not in vistos:
                    vistos.add(clausula)
                    filtros.append(clausula)
    return filtros


def _where_por_campos(dataset, pares):
    partes = []
    for candidatos, valor in pares:
        if valor in (None, ""):
            continue
        campo = _campo_existente(dataset, candidatos)
        if campo:
            partes.append(_clausula_igual(dataset, campo, valor))
    return " AND ".join(partes)


def _where_por_campos_flexivel(dataset, pares):
    filtros = []
    combinacao = _where_por_campos(dataset, pares)
    if combinacao:
        filtros.append(combinacao)

    if len(pares) > 1:
        for indice in range(len(pares)):
            parcial = _where_por_campos(dataset, [pares[indice]])
            if parcial and parcial not in filtros:
                filtros.append(parcial)

    for clausula in _montar_filtros_atributo(dataset, pares):
        if clausula not in filtros:
            filtros.append(clausula)

    return filtros


def _filtros_export_reurb(dataset, numero, bairro=None):
    """Prioriza filtro por n_coletivo; bairro/nome entra apenas como fallback."""
    filtros = []
    pares_numero = [(["n_coletivo", "coletivo", "reurb"], numero)]

    parcial_numero = _where_por_campos(dataset, pares_numero)
    if parcial_numero:
        filtros.append(parcial_numero)
    for clausula in _montar_filtros_atributo(dataset, pares_numero):
        if clausula not in filtros:
            filtros.append(clausula)

    if not bairro:
        return filtros

    pares_completo = pares_numero + [(["bairro", "nome"], bairro)]
    combinacao = _where_por_campos(dataset, pares_completo)
    if combinacao and combinacao not in filtros:
        filtros.append(combinacao)

    parcial_bairro = _where_por_campos(dataset, [(["bairro", "nome"], bairro)])
    if parcial_bairro and parcial_bairro not in filtros:
        filtros.append(parcial_bairro)

    for clausula in _montar_filtros_atributo(dataset, [(["bairro", "nome"], bairro)]):
        if clausula not in filtros:
            filtros.append(clausula)

    return filtros


def _camada_aprx_por_nome(aprx_path, nomes):
    nomes_normalizados = {str(nome).strip().lower() for nome in nomes}
    aprx = arcpy.mp.ArcGISProject(str(aprx_path))
    for mapa in aprx.listMaps():
        for layer in mapa.listLayers():
            try:
                if layer.isFeatureLayer and str(layer.name).strip().lower() in nomes_normalizados:
                    return layer
            except Exception:
                pass
    raise ValueError(f"Camada nao encontrada no APRX {aprx_path}: {', '.join(nomes)}")


def _camada_aprx_por_nome_opcional(aprx_path, nomes):
    try:
        return _camada_aprx_por_nome(aprx_path, nomes)
    except Exception:
        return None


def _contar_features(dataset):
    return int(arcpy.management.GetCount(dataset)[0])


def _dataset_tem_features(dataset):
    try:
        return bool(dataset and arcpy.Exists(dataset) and _contar_features(dataset) > 0)
    except Exception:
        return False


def _limpar_selecao_layer(layer):
    try:
        arcpy.management.SelectLayerByAttribute(layer, "CLEAR_SELECTION")
    except Exception:
        pass


def _exportar_feature_por_localizacao(origem, referencia_fc, saida, relacao="INTERSECT"):
    saida = str(saida)
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    origem_layer = f"lyr_exp_loc_{slug_resultado(Path(saida).stem)}"
    ref_layer = f"lyr_ref_loc_{slug_resultado(Path(saida).stem)}"
    try:
        _limpar_selecao_layer(origem)
        _limpar_selecao_layer(referencia_fc)
        arcpy.management.MakeFeatureLayer(origem, origem_layer)
        arcpy.management.MakeFeatureLayer(referencia_fc, ref_layer)
        _limpar_selecao_layer(origem_layer)
        _limpar_selecao_layer(ref_layer)
        arcpy.management.SelectLayerByLocation(
            origem_layer,
            relacao,
            ref_layer,
            selection_type="NEW_SELECTION",
        )
        total = _contar_features(origem_layer)
        if total == 0:
            raise ValueError(f"Nenhum registro intersectou a referencia para exportar: {saida}")
        arcpy.management.CopyFeatures(origem_layer, saida)
        arcpy.AddMessage(
            f"Exportacao espacial ({relacao}) de {Path(saida).name}: {total} feicoes"
        )
        return saida
    finally:
        for layer in [origem_layer, ref_layer]:
            try:
                arcpy.management.Delete(layer)
            except Exception:
                pass


def _exportar_feature_filtrado(origem, saida, filtros, referencia_espacial=None, relacao="INTERSECT"):
    saida = str(saida)
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    ultimo_erro = None
    filtros = [item for item in (filtros or []) if item]
    for where in filtros:
        nome_layer = f"lyr_export_{slug_resultado(Path(saida).stem)}"
        try:
            _limpar_selecao_layer(origem)
            arcpy.management.MakeFeatureLayer(origem, nome_layer, where or None)
            if _contar_features(nome_layer) > 0:
                total = _contar_features(nome_layer)
                arcpy.management.CopyFeatures(nome_layer, saida)
                arcpy.management.Delete(nome_layer)
                arcpy.AddMessage(
                    f"Exportacao por atributo de {Path(saida).name}: {total} feicoes"
                )
                return saida
            arcpy.management.Delete(nome_layer)
        except Exception as exc:
            ultimo_erro = exc
            try:
                arcpy.management.Delete(nome_layer)
            except Exception:
                pass
    if referencia_espacial and arcpy.Exists(referencia_espacial):
        try:
            return _exportar_feature_por_localizacao(origem, referencia_espacial, saida, relacao)
        except Exception as exc:
            ultimo_erro = exc
    if ultimo_erro:
        raise ultimo_erro
    raise ValueError(f"Nenhum registro encontrado para exportar: {saida}")


def _exportar_por_n_coletivo_ou_bairro(layer, shp_bairro, numero, saida):
    """Exporta pelo n_coletivo; se vier pouco, usa intersecao com o bairro do coletivo."""
    saida = Path(saida)
    filtros_numero = _filtros_export_reurb(layer, numero, bairro=None)
    total_numero = 0

    try:
        _exportar_feature_filtrado(layer, saida, filtros_numero, referencia_espacial=None)
        total_numero = _contar_features(saida)
    except Exception:
        total_numero = 0

    total_espacial = 0
    saida_espacial = saida.with_name(f"{saida.stem}_espacial.shp")
    try:
        _exportar_feature_por_localizacao(layer, shp_bairro, saida_espacial)
        total_espacial = _contar_features(saida_espacial)
    except Exception as exc:
        arcpy.AddWarning(f"Selecao espacial nao gerou feicoes para {saida.name}: {exc}")

    usar_espacial = (
        total_espacial > 0
        and (
            total_numero == 0
            or total_espacial >= max(total_numero + 5, total_numero * 1.25)
        )
    )

    if usar_espacial:
        if arcpy.Exists(str(saida)):
            arcpy.management.Delete(str(saida))
        arcpy.management.CopyFeatures(str(saida_espacial), str(saida))
        arcpy.AddMessage(
            f"Exportacao de {saida.name}: {total_espacial} feicoes "
            f"(intersecao com bairro do n_coletivo {numero})"
        )
    elif total_numero > 0:
        arcpy.AddMessage(
            f"Exportacao de {saida.name}: {total_numero} feicoes (n_coletivo {numero})"
        )
        if total_espacial > total_numero:
            arcpy.AddMessage(
                f"Selecao espacial de {saida.name} ignorada para evitar feicoes vizinhas: "
                f"{total_espacial} espaciais contra {total_numero} por n_coletivo"
            )
    else:
        raise ValueError(f"Nenhum registro encontrado para exportar: {saida}")

    if arcpy.Exists(str(saida_espacial)):
        arcpy.management.Delete(str(saida_espacial))
    return str(saida)


def _exportar_eixo_por_bairro(origem_eixo, bairro_fc, saida):
    saida = str(saida)
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    eixo_layer = f"lyr_eixo_{slug_resultado(Path(saida).stem)}"
    bairro_layer = f"lyr_bairro_{slug_resultado(Path(saida).stem)}"
    try:
        arcpy.management.MakeFeatureLayer(origem_eixo, eixo_layer)
        arcpy.management.MakeFeatureLayer(bairro_fc, bairro_layer)
        arcpy.management.SelectLayerByLocation(eixo_layer, "INTERSECT", bairro_layer, selection_type="NEW_SELECTION")
        if _contar_features(eixo_layer) == 0:
            arcpy.AddWarning("Nenhum eixo viario intersectou o bairro; copiando camada de eixo completa.")
            arcpy.management.SelectLayerByAttribute(eixo_layer, "CLEAR_SELECTION")
        arcpy.management.CopyFeatures(eixo_layer, saida)
    finally:
        for layer in [eixo_layer, bairro_layer]:
            try:
                arcpy.management.Delete(layer)
            except Exception:
                pass
    return saida


def _caminho_aprx_camadas(input_json):
    return (
        input_json.get("aprxCamadas")
        or input_json.get("camadas")
        or input_json.get("projetoCamadasArcGIS")
    )


def _normalizar_input_json(input_json):
    if not isinstance(input_json, dict):
        return input_json

    normalizado = dict(input_json)
    dados = dict(normalizado.get("dados") or {})

    aprx_camadas = _caminho_aprx_camadas(normalizado)
    if aprx_camadas and not normalizado.get("aprxCamadas"):
        normalizado["aprxCamadas"] = aprx_camadas

    for chave in ("responsavelTecnico", "anexarLista", "rasterSituacao", "tipoPrancha", "exportarCamadasArcGIS"):
        if normalizado.get(chave) in (None, "") and dados.get(chave) not in (None, ""):
            normalizado[chave] = dados[chave]

    shp_lotes = (
        normalizado.get("shpLotes")
        or dados.get("shpLotes")
        or dados.get("lotes")
    )
    exportar = bool(normalizado.get("exportarCamadasArcGIS") or normalizado.get("usarCamadasArcGIS"))
    if aprx_camadas and not shp_lotes and not exportar:
        normalizado["exportarCamadasArcGIS"] = True

    normalizado["dados"] = dados
    return normalizado


def _preparar_input_com_camadas_arcgis(input_json):
    input_json = _normalizar_input_json(input_json)
    usar = bool(input_json.get("exportarCamadasArcGIS") or input_json.get("usarCamadasArcGIS"))
    aprx_informado = _caminho_aprx_camadas(input_json)
    dados = input_json.get("dados", {}) or {}
    if not usar and not aprx_informado:
        return input_json

    numero = dados.get("numeroProcessoColetivo") or input_json.get("numeroProcessoColetivo")
    bairro = dados.get("bairro") or input_json.get("bairro")
    municipio = dados.get("municipio") or input_json.get("municipio") or "municipio"
    if not numero:
        raise ValueError("Informe dados.numeroProcessoColetivo para exportar as camadas atuais do ArcGIS.")
    if not bairro:
        raise ValueError("Informe dados.bairro para exportar as camadas atuais do ArcGIS.")

    aprx_camadas = _caminho_aprx_camadas(input_json) or r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx"
    if not Path(aprx_camadas).exists():
        raise ValueError(f"APRX das camadas nao encontrado: {aprx_camadas}")

    nomes = input_json.get("camadasArcGIS") or {}
    layer_lotes = _camada_aprx_por_nome(aprx_camadas, [nomes.get("lotes", "Lotes")])
    layer_bairro = _camada_aprx_por_nome(aprx_camadas, [nomes.get("bairro", "Bairro")])
    layer_quadras = _camada_aprx_por_nome(aprx_camadas, [nomes.get("quadras", "Quadras")])
    layer_eixo = _camada_aprx_por_nome(aprx_camadas, [nomes.get("eixoViario", "Eixo Viario"), nomes.get("eixo", "Eixo Viario")])
    layer_frente = None
    if bool(input_json.get("exportarMarcacaoFrenteArcGIS", False)):
        layer_frente = _camada_aprx_por_nome_opcional(
            aprx_camadas,
            [
            nomes.get("marcacaoFrente", "marcacao_frente_lote_ma_reurb"),
            nomes.get("frenteLote", "marcacao_frente_lote_ma_reurb"),
            "Marcação de Frente",
            "Marcacao da frente",
            ],
        )

    pasta_saida = input_json.get("pastaSaida") or dados.get("pastaSaida")
    pasta_base = Path(pasta_saida).parent if pasta_saida else Path(__file__).parent / "dados_exportados_arcgis"
    pasta = pasta_base / slug_resultado(municipio) / slug_resultado(bairro) / slug_resultado(numero)
    pasta.mkdir(parents=True, exist_ok=True)

    where_bairro = _filtros_export_reurb(layer_bairro, numero, bairro)
    where_bairro_nome = _where_por_campos(layer_bairro, [
        (["nome", "bairro"], bairro),
    ])
    where_frente_completo = None
    where_frente_numero = None
    where_frente_bairro = None
    if layer_frente:
        where_frente_numero = _where_por_campos(layer_frente, [
            (["n_coletivo", "coletivo", "reurb"], numero),
        ])
        where_frente_completo = _where_por_campos(layer_frente, [
            (["n_coletivo", "coletivo", "reurb"], numero),
            (["bairro"], bairro),
            (["municipio"], municipio),
        ])
        where_frente_bairro = _where_por_campos(layer_frente, [
            (["bairro"], bairro),
            (["municipio"], municipio),
        ])

    shp_bairro = _exportar_feature_filtrado(
        layer_bairro,
        pasta / "bairro.shp",
        where_bairro + ([where_bairro_nome] if where_bairro_nome else []),
    )
    shp_lotes = _exportar_por_n_coletivo_ou_bairro(layer_lotes, shp_bairro, numero, pasta / "lotes.shp")
    shp_quadras = _exportar_por_n_coletivo_ou_bairro(layer_quadras, shp_bairro, numero, pasta / "quadras.shp")
    simbologia_quadras = _exportar_simbologia_camada(layer_quadras, pasta / "quadras.lyrx")
    eixo_viario = _exportar_eixo_por_bairro(layer_eixo, shp_bairro, pasta / "eixo_viario.shp")
    shp_frente_lotes = input_json.get("shpFrenteLotes") or input_json.get("pontosFrenteLotes") or dados.get("shpFrenteLotes")
    if layer_frente:
        try:
            shp_frente_lotes = _exportar_feature_filtrado(
                layer_frente,
                pasta / "marcacao_frente_lote.shp",
                [where_frente_numero, where_frente_completo, where_frente_bairro],
            )
        except Exception as exc:
            arcpy.AddWarning(f"Marcacao de frente nao exportada: {exc}")

    atualizado = dict(input_json)
    atualizado["shpLotes"] = shp_lotes
    atualizado["shpBairro"] = shp_bairro
    atualizado["shpQuadras"] = shp_quadras
    if simbologia_quadras:
        atualizado["simbologiaQuadras"] = simbologia_quadras
    atualizado["eixoViario"] = eixo_viario
    if shp_frente_lotes:
        atualizado["shpFrenteLotes"] = shp_frente_lotes
    atualizado["camadasExportadasArcGIS"] = {
        "aprx": str(aprx_camadas),
        "pasta": str(pasta),
        "lotes": shp_lotes,
        "bairro": shp_bairro,
        "quadras": shp_quadras,
        "simbologiaQuadras": simbologia_quadras,
        "eixoViario": eixo_viario,
        "marcacaoFrente": shp_frente_lotes,
    }
    arcpy.AddMessage(f"Camadas atuais exportadas do ArcGIS Pro em: {pasta}")
    arcpy.AddMessage(f"Filtro principal: n_coletivo = {numero}")
    arcpy.AddMessage(f"Lotes exportados: {_contar_features(shp_lotes)}")
    arcpy.AddMessage(f"Bairro exportado: {_contar_features(shp_bairro)}")
    arcpy.AddMessage(f"Quadras exportadas: {_contar_features(shp_quadras)}")
    arcpy.AddMessage(f"Eixos exportados: {_contar_features(eixo_viario)}")
    if shp_frente_lotes:
        arcpy.AddMessage(f"Marcacoes de frente usadas: {_contar_features(shp_frente_lotes)}")
    return atualizado


def _aplicar_simbolo_poligono(layer, cor):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            symbol.color = {"RGB": cor}
            try:
                symbol.outlineColor = {"RGB": [70, 70, 70, 100]}
                symbol.outlineWidth = 0.35
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbolo em {layer.name}: {exc}")


def _aplicar_simbolo_bairro(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            symbol.color = {"RGB": [245, 245, 245, 0]}
            try:
                symbol.outlineColor = {"RGB": [180, 0, 0, 100]}
                symbol.outlineWidth = 1.2
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia do bairro: {exc}")


def _aplicar_simbolo_contorno(layer, cor_linha=None, espessura=0.45):
    cor_linha = cor_linha or [255, 255, 255, 100]
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            try:
                symbol.color = {"RGB": [255, 255, 255, 0]}
            except Exception:
                pass
            try:
                symbol.outlineColor = {"RGB": cor_linha}
                symbol.outlineWidth = espessura
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar contorno em {layer.name}: {exc}")


def _aplicar_simbologia_arquivo(layer, caminho_simbologia):
    try:
        if caminho_simbologia and Path(caminho_simbologia).exists():
            arcpy.ApplySymbologyFromLayer_management(
                in_layer=layer,
                in_symbology_layer=str(caminho_simbologia),
                symbology_fields=None,
                update_symbology="DEFAULT",
            )
            return True
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia {caminho_simbologia}: {exc}")
    return False


def _exportar_simbologia_camada(layer, caminho_lyrx):
    if not layer:
        return None
    caminho_lyrx = Path(caminho_lyrx)
    try:
        if caminho_lyrx.exists():
            caminho_lyrx.unlink()
    except Exception:
        pass
    try:
        layer.saveACopy(str(caminho_lyrx))
        arcpy.AddMessage(f"Simbologia exportada: {caminho_lyrx}")
        return str(caminho_lyrx)
    except Exception as exc_save:
        try:
            arcpy.management.SaveToLayerFile(layer, str(caminho_lyrx), "ABSOLUTE", "INDEXED")
            arcpy.AddMessage(f"Simbologia exportada: {caminho_lyrx}")
            return str(caminho_lyrx)
        except Exception as exc_layerfile:
            arcpy.AddWarning(
                f"Nao foi possivel exportar simbologia de {getattr(layer, 'name', 'camada')}: "
                f"{exc_save}; {exc_layerfile}"
            )
    return None


def _desativar_rotulos(layer):
    try:
        layer.showLabels = False
        for label_class in layer.listLabelClasses():
            label_class.visible = False
    except Exception:
        pass


def _adicionar_camada_bairro(aprx_map, shp_bairro, bairro=None):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        arcpy.AddWarning("Camada de bairro nao informada/encontrada. A planta seguira somente com lotes.")
        return None
    layer = aprx_map.addDataFromPath(shp_bairro)
    layer.name = f"Bairro {bairro}" if bairro else "Bairro"
    _aplicar_simbolo_bairro(layer)
    arcpy.AddMessage(f"Camada de bairro adicionada ao fundo: {shp_bairro}")
    return layer


def _obter_mapa(aprx, nome, fallback_index=0):
    for mapa in aprx.listMaps():
        if mapa.name == nome:
            return mapa
    mapas = aprx.listMaps()
    if len(mapas) > fallback_index:
        mapas[fallback_index].name = nome
        return mapas[fallback_index]
    try:
        return aprx.createMap(nome)
    except Exception:
        return mapas[0]


def _expandir_extent(extent, fator):
    if not extent or fator <= 1:
        return extent
    centro_x = (extent.XMin + extent.XMax) / 2.0
    centro_y = (extent.YMin + extent.YMax) / 2.0
    metade_largura = (extent.XMax - extent.XMin) * fator / 2.0
    metade_altura = (extent.YMax - extent.YMin) * fator / 2.0
    novo = arcpy.Extent(
        centro_x - metade_largura,
        centro_y - metade_altura,
        centro_x + metade_largura,
        centro_y + metade_altura,
    )
    novo.spatialReference = extent.spatialReference
    return novo


def _arredondar_escala_mapa(escala, margem=1.12):
    escala = float(escala or 0) * margem
    if escala >= 100000:
        return (((escala // 5000) + 1) * 5000)
    if escala >= 10000:
        return (((escala // 500) + 1) * 500)
    if escala >= 1000:
        return (((escala // 100) + 1) * 100)
    return (((escala // 50) + 1) * 50)


def _adicionar_basemap_imagery_esri(mapa):
    try:
        mapa.addBasemap("Imagery")
        arcpy.AddMessage("Basemap Esri Imagery adicionado na planta de situacao.")
        return True
    except Exception as exc_basemap:
        arcpy.AddWarning(f"Basemap Esri indisponivel ({exc_basemap}); tentando World Imagery.")
    try:
        mapa.addDataFromPath(WORLD_IMAGERY_URL)
        arcpy.AddMessage("World Imagery (ArcGIS Online) adicionado na planta de situacao.")
        return True
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel adicionar World Imagery na planta de situacao: {exc}")
    return False


def _adicionar_camada_perimetro_situacao(mapa, shp_bairro):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        return None
    bairro_layer = mapa.addDataFromPath(shp_bairro)
    bairro_layer.name = "Perimetro overview"
    if not _aplicar_simbologia_arquivo(bairro_layer, SIMBOLOGIA_PERIMETRO_OVERVIEW):
        _aplicar_simbolo_contorno(bairro_layer, [255, 0, 0, 100], 1.8)
    _desativar_rotulos(bairro_layer)
    return bairro_layer


def _preparar_mapa_situacao(
    aprx,
    shp_lotes,
    shp_bairro,
    raster_situacao=None,
    preferir_imagery_esri=True,
    usar_raster_local=False,
):
    mapa = _obter_mapa(aprx, "OVERVIEW_MAP_FRAME", fallback_index=1)
    _limpar_mapa(mapa)

    if preferir_imagery_esri:
        _adicionar_basemap_imagery_esri(mapa)
    elif raster_situacao and arcpy.Exists(raster_situacao):
        raster_layer = mapa.addDataFromPath(raster_situacao)
        raster_layer.name = "Imagem de satelite"
        arcpy.AddMessage(f"Raster local adicionado na planta de situacao: {raster_situacao}")
    else:
        _adicionar_basemap_imagery_esri(mapa)

    if usar_raster_local and raster_situacao and arcpy.Exists(raster_situacao):
        raster_layer = mapa.addDataFromPath(raster_situacao)
        raster_layer.name = "Ortofoto local"
        try:
            mapa.moveLayer(raster_layer, "BOTTOM")
        except Exception:
            pass
        arcpy.AddMessage(f"Ortofoto local sobreposta na planta de situacao: {raster_situacao}")

    _adicionar_camada_perimetro_situacao(mapa, shp_bairro)
    return mapa


def _ajustar_extent_situacao(frame, feature_situacao, fator_buffer=FATOR_ZOOM_PLANTA_SITUACAO):
    extent = arcpy.Describe(feature_situacao).extent
    extent = _expandir_extent(extent, fator_buffer)
    frame.camera.setExtent(extent)
    frame.camera.scale = _arredondar_escala_mapa(frame.camera.scale, margem=1.08)
    try:
        frame.camera.setExtent(frame.camera.getExtent())
    except Exception:
        pass


def _opcoes_planta_situacao(input_json=None):
    input_json = input_json or {}
    dados = input_json.get("dados") or {}
    usar_raster_local = bool(
        input_json.get("usarRasterLocalSituacao")
        or dados.get("usarRasterLocalSituacao")
    )
    preferir_imagery_esri = not bool(
        input_json.get("desativarImageryEsriSituacao")
        or dados.get("desativarImageryEsriSituacao")
    )
    fator = (
        input_json.get("zoomPlantaSituacao")
        or dados.get("zoomPlantaSituacao")
        or FATOR_ZOOM_PLANTA_SITUACAO
    )
    try:
        fator = float(fator)
    except Exception:
        fator = FATOR_ZOOM_PLANTA_SITUACAO
    if usar_raster_local and not preferir_imagery_esri:
        preferir_imagery_esri = False
    return {
        "preferir_imagery_esri": preferir_imagery_esri,
        "usar_raster_local": usar_raster_local,
        "fator_zoom_situacao": max(fator, 1.5),
    }


def _montar_mapa_situacao_e_extent(
    aprx,
    layout,
    aprx_map,
    shp_lotes,
    shp_bairro,
    feature_extent,
    feature_situacao,
    raster_situacao=None,
    opcoes_situacao=None,
):
    opcoes = opcoes_situacao or _opcoes_planta_situacao()
    mapa_situacao = _preparar_mapa_situacao(
        aprx,
        shp_lotes,
        shp_bairro,
        raster_situacao=raster_situacao,
        preferir_imagery_esri=opcoes["preferir_imagery_esri"],
        usar_raster_local=opcoes["usar_raster_local"],
    )
    escala = _ajustar_extent(
        layout,
        aprx_map,
        feature_extent,
        mapa_situacao=mapa_situacao,
        feature_situacao=feature_situacao,
        fator_zoom_situacao=opcoes["fator_zoom_situacao"],
    )
    return mapa_situacao, escala


def _area_perimetro_bairro(shp_bairro):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        return None, None
    sr_utm = arcpy.SpatialReference(31983)
    area = 0.0
    perimetro = 0.0
    with arcpy.da.SearchCursor(shp_bairro, ["SHAPE@"]) as cursor:
        for row in cursor:
            geom = row[0]
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            area += float(getattr(geom, "area", 0) or 0)
            perimetro += float(getattr(geom, "length", 0) or 0)
    return area, perimetro


def _ocultar_simbolo(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            try:
                symbol.color = {"RGB": [0, 0, 0, 0]}
            except Exception:
                pass
            try:
                symbol.outlineColor = {"RGB": [0, 0, 0, 0]}
                symbol.outlineWidth = 0
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception:
        pass


def _configurar_rotulos_lotes(layer, campo_quadra, campo_lote):
    try:
        expressao_lote = (
            f"'L' + IIf(IsNan(Number($feature.{campo_lote})), "
            f"Text($feature.{campo_lote}), Right('00' + Text(Number($feature.{campo_lote}), '#'), 2))"
        )
        layer.showLabels = True
        for label_class in layer.listLabelClasses():
            label_class.expression = expressao_lote
            try:
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            label_class.visible = True

        cim = layer.getDefinition("V3")
        for label_class in getattr(cim, "labelClasses", []):
            label_class.visible = True
            try:
                label_class.expression = expressao_lote
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            text_symbol = getattr(label_class, "textSymbol", None)
            if text_symbol is not None:
                _ajustar_text_symbol(text_symbol, 3.2)
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel configurar rotulos dos lotes: {exc}")


def _ajustar_text_symbol(simbolo, tamanho):
    visitados = set()

    def ajustar(objeto, profundidade=0):
        if objeto is None or profundidade > 4:
            return
        obj_id = id(objeto)
        if obj_id in visitados:
            return
        visitados.add(obj_id)
        for prop in ["size", "fontSize", "height", "textSize"]:
            try:
                if hasattr(objeto, prop):
                    setattr(objeto, prop, tamanho)
            except Exception:
                pass
        for prop in ["symbol", "symbolReference", "textSymbol"]:
            try:
                if hasattr(objeto, prop):
                    ajustar(getattr(objeto, prop), profundidade + 1)
            except Exception:
                pass
        for prop in ["symbolLayers", "layers"]:
            try:
                for item in getattr(objeto, prop, []) or []:
                    ajustar(item, profundidade + 1)
            except Exception:
                pass

    ajustar(simbolo)


def _configurar_texto_lote(simbolo, tamanho):
    _ajustar_text_symbol(simbolo, tamanho)
    visitados = set()

    def ajustar(objeto, profundidade=0):
        if objeto is None or profundidade > 5:
            return
        obj_id = id(objeto)
        if obj_id in visitados:
            return
        visitados.add(obj_id)
        try:
            if hasattr(objeto, "color"):
                objeto.color.values = [20, 20, 20, 100]
        except Exception:
            pass
        try:
            if hasattr(objeto, "haloSize"):
                objeto.haloSize = 0.55
        except Exception:
            pass
        try:
            if hasattr(objeto, "haloSymbol") and objeto.haloSymbol:
                ajustar(objeto.haloSymbol, profundidade + 1)
        except Exception:
            pass
        for prop in ["symbol", "symbolReference", "textSymbol"]:
            try:
                if hasattr(objeto, prop):
                    ajustar(getattr(objeto, prop), profundidade + 1)
            except Exception:
                pass
        for prop in ["symbolLayers", "layers"]:
            try:
                for item in getattr(objeto, prop, []) or []:
                    ajustar(item, profundidade + 1)
            except Exception:
                pass

    ajustar(simbolo)


def _configurar_texto_quadra(simbolo, tamanho):
    _ajustar_text_symbol(simbolo, tamanho)
    visitados = set()

    def ajustar(objeto, profundidade=0):
        if objeto is None or profundidade > 5:
            return
        obj_id = id(objeto)
        if obj_id in visitados:
            return
        visitados.add(obj_id)
        try:
            if hasattr(objeto, "color"):
                objeto.color.values = [210, 25, 25, 100]
        except Exception:
            pass
        for prop in ["fontStyleName", "styleName", "fontStyle", "fontWeight"]:
            try:
                if hasattr(objeto, prop):
                    valor = 700 if prop == "fontWeight" else "Bold"
                    setattr(objeto, prop, valor)
            except Exception:
                pass
        try:
            if hasattr(objeto, "haloSize"):
                objeto.haloSize = 0.75
        except Exception:
            pass
        try:
            if hasattr(objeto, "haloSymbol") and objeto.haloSymbol:
                ajustar(objeto.haloSymbol, profundidade + 1)
        except Exception:
            pass
        for prop in ["symbol", "symbolReference", "textSymbol"]:
            try:
                if hasattr(objeto, prop):
                    ajustar(getattr(objeto, prop), profundidade + 1)
            except Exception:
                pass
        for prop in ["symbolLayers", "layers"]:
            try:
                for item in getattr(objeto, prop, []) or []:
                    ajustar(item, profundidade + 1)
            except Exception:
                pass

    ajustar(simbolo)


def _adicionar_rotulos_lotes(aprx_map, shp_lotes):
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    campo_lote = _campo_existente(shp_lotes, ["lote"])
    if not campo_quadra or not campo_lote:
        raise ValueError("Campos 'quadra' e/ou 'lote' nao encontrados no shapefile de lotes.")

    rotulos = aprx_map.addDataFromPath(shp_lotes)
    rotulos.name = "Rotulos dos lotes"
    _ocultar_simbolo(rotulos)
    _configurar_rotulos_lotes(rotulos, campo_quadra, campo_lote)


def _adicionar_camada_quadras_loteamento(aprx_map, shp_lotes, pasta, shp_quadras=None, simbologia_quadras=None):
    if _dataset_tem_features(shp_quadras):
        quadras_fc = shp_quadras
    else:
        try:
            quadras_fc, _ = _dissolver_quadras(shp_lotes, pasta)
        except Exception as exc:
            arcpy.AddWarning(f"Camada de quadras nao adicionada: {exc}")
            return None

    quadras_layer = aprx_map.addDataFromPath(quadras_fc)
    quadras_layer.name = "Quadras"
    _aplicar_simbologia_quadras(quadras_layer, simbologia_quadras)
    campo_quadra = _campo_existente(quadras_fc, ["quadra"])
    if campo_quadra:
        _configurar_rotulos_quadras(quadras_layer, campo_quadra)
    arcpy.AddMessage(f"Camada de quadras adicionada: {_contar_features(quadras_fc)} feicoes")
    return quadras_layer


def _adicionar_camadas_lotes(aprx_map, shp_lotes, incluir_rotulos=True):
    campo_status = _campo_existente(shp_lotes, ["status"])
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    campo_lote = _campo_existente(shp_lotes, ["lote"])
    if not campo_status:
        raise ValueError("Campo 'status' nao encontrado no shapefile de lotes.")
    if not campo_quadra or not campo_lote:
        raise ValueError("Campos 'quadra' e/ou 'lote' nao encontrados no shapefile de lotes.")

    contagens = {}
    with arcpy.da.SearchCursor(shp_lotes, [campo_status]) as cursor:
        for row in cursor:
            try:
                status = int(row[0] or 0)
            except Exception:
                status = 0
            contagens[status] = contagens.get(status, 0) + 1

    for status, (descricao, cor) in reversed(list(STATUS_LEGENDA.items())):
        if contagens.get(status, 0) == 0 and status != 0:
            continue
        layer = aprx_map.addDataFromPath(shp_lotes)
        layer.name = f"{status} - {descricao} ({contagens.get(status, 0)})"
        try:
            layer.definitionQuery = _where_status(campo_status, status)
        except Exception:
            pass
        _aplicar_simbolo_poligono(layer, cor)

    if incluir_rotulos:
        _adicionar_rotulos_lotes(aprx_map, shp_lotes)
    return contagens


def _ajustar_extent(
    layout,
    aprx_map,
    feature_extent,
    mapa_situacao=None,
    feature_situacao=None,
    fator_zoom_situacao=FATOR_ZOOM_PLANTA_SITUACAO,
):
    frames = layout.listElements("MAPFRAME_ELEMENT", "MAP_FRAME")
    if not frames:
        frames = layout.listElements("MAPFRAME_ELEMENT")
    if not frames:
        raise ValueError("Layout nao possui MAP_FRAME.")

    map_frame = frames[0]
    map_frame.map = aprx_map
    extent = arcpy.Describe(feature_extent).extent
    map_frame.camera.setExtent(extent)
    escala = _arredondar_escala_mapa(map_frame.camera.scale, margem=1.20)
    map_frame.camera.scale = escala
    aprx_map.defaultCamera = map_frame.camera

    feature_situacao = feature_situacao if feature_situacao and arcpy.Exists(feature_situacao) else feature_extent
    for frame in layout.listElements("MAPFRAME_ELEMENT", "OVERVIEW_MAP_FRAME"):
        try:
            frame.map = mapa_situacao or aprx_map
            _ajustar_extent_situacao(frame, feature_situacao, fator_zoom_situacao)
        except Exception as exc:
            arcpy.AddWarning(f"Nao foi possivel ajustar enquadramento da planta de situacao: {exc}")

    return int(escala)


def _texto_existente(layout, nome, texto, x=None, y=None, tamanho=8, largura=None):
    elementos = layout.listElements("TEXT_ELEMENT", nome)
    if elementos:
        elementos[0].text = texto
        elementos[0].visible = True
        if x is not None:
            try:
                elementos[0].elementPositionX = x
            except Exception:
                pass
        if y is not None:
            try:
                elementos[0].elementPositionY = y
            except Exception:
                pass
        if largura:
            try:
                elementos[0].elementWidth = largura
            except Exception:
                pass
        return elementos[0]

    if not hasattr(layout, "createTextElement") or x is None or y is None:
        return None

    elemento = layout.createTextElement(arcpy.Point(x, y), "POINT", texto, tamanho, "Arial", "Regular")
    elemento.name = nome
    if largura:
        try:
            elemento.elementWidth = largura
        except Exception:
            pass
    return elemento


def _atualizar_textos_padrao(
    layout,
    numero,
    municipio,
    bairro,
    total_lotes,
    total_beneficiarios,
    escala,
    area_bairro=None,
    perimetro_bairro=None,
    responsavel_tecnico=None,
):
    hoje = datetime.now().strftime("%d/%m/%Y")
    area_texto = decimal_texto(area_bairro) if area_bairro else ""
    perimetro_texto = decimal_texto(perimetro_bairro) if perimetro_bairro else ""
    responsavel_tecnico = responsavel_tecnico or {}
    nome_responsavel = responsavel_tecnico.get("nome", "")
    formacao_responsavel = responsavel_tecnico.get("formacao", "")
    registro_responsavel = responsavel_tecnico.get("registro", "")
    substituicoes = {
        "{bairro}": bairro,
        "{municipio}": municipio,
        "{area}": area_texto,
        "{matricula}": numero,
        "{folha}": "02",
        "{perimetro}": perimetro_texto,
        "{data}": hoje,
        "{fusoutm}": "23S",
        "{responsavel_tecnico}": nome_responsavel,
        "{funcao}": formacao_responsavel,
        "{n_crea_cau}": registro_responsavel,
    }
    for elemento in layout.listElements("TEXT_ELEMENT"):
        try:
            texto = elemento.text
            if str(texto).strip() == "{bairro}":
                elemento.text = ""
                continue
            texto = texto.replace("Matrícula:", "Processo:")
            texto = texto.replace("Matricula:", "Processo:")
            texto = texto.replace("Total de lotes:", "Área (m²):")
            texto = texto.replace("Beneficiários:", "Perímetro (m):")
            texto = texto.replace("Beneficiarios:", "Perímetro (m):")
            elemento.text = texto
            for chave, valor in substituicoes.items():
                if chave in elemento.text or chave == elemento.name:
                    elemento.text = elemento.text.replace(chave, valor)
            if "Planta Perimetro" in elemento.text or "Planta Perímetro" in elemento.text:
                elemento.text = f"PLANTA LOTEAMENTO {bairro.upper()}"
            if "Regularização Fundiária Urbana" in elemento.text or "Regularizacao Fundiaria Urbana" in elemento.text:
                elemento.text = "Regularização Fundiária Urbana - REURB"
            if "PLANTA LOTEAMENTO" in elemento.text:
                elemento.text = f"PLANTA LOTEAMENTO {bairro.upper()}"
        except Exception:
            pass

    _texto_existente(
        layout,
        "titulo_prancha_loteamento",
        f"PLANTA LOTEAMENTO {bairro.upper()}",
        x=13.1,
        y=27.35,
        tamanho=13,
        largura=18.0,
    )
    _texto_existente(
        layout,
        "subtitulo_prancha_loteamento",
        "",
        x=13.1,
        y=26.95,
        tamanho=8,
        largura=18.0,
    )
    _texto_existente(
        layout,
        "carimbo_prancha_loteamento",
        (
            "Legenda - Status dos Lotes\n"
            + "\n".join(f"{codigo} - {descricao}" for codigo, (descricao, _) in STATUS_LEGENDA.items())
            + "\n\nDados da Prancha\n"
            f"Municipio: {municipio}\n"
            f"Bairro: {bairro}\n"
            f"Processo: {numero}\n"
            f"Area do bairro (m2): {area_texto}\n"
            f"Perimetro do bairro (m): {perimetro_texto}\n"
            f"Total de lotes: {total_lotes}\n"
            f"Beneficiarios listados: {total_beneficiarios}\n"
            "Sistema: SIRGAS 2000 / UTM 23S\n"
            f"Escala aproximada: 1:{escala}"
        ),
        x=21.8,
        y=24.2,
        tamanho=6.2,
        largura=14.8,
    )

    _texto_existente(
        layout,
        "titulo_planta_situacao_loteamento",
        "Planta de Situação:",
        x=21.8,
        y=13.15,
        tamanho=7.0,
        largura=4.0,
    )


def _ocultar_tabelas(layout):
    for tabela in layout.listElements("TABLEFRAME_ELEMENT"):
        try:
            tabela.visible = False
        except Exception:
            pass


def _criar_legenda_layout(layout, map_frame, contagens, bairro=None):
    for legenda in list(layout.listElements("LEGEND_ELEMENT")):
        try:
            layout.deleteElement(legenda)
        except Exception:
            try:
                legenda.visible = False
            except Exception:
                pass

    ponto_inicial = arcpy.Point(257.0, 284.0)
    legenda = layout.createMapSurroundElement(
        ponto_inicial,
        "LEGEND",
        map_frame,
        None,
        "LEGENDA_STATUS_LOTES",
    )
    try:
        legenda.setAnchor("TOP_LEFT_CORNER")
    except Exception:
        pass
    legenda.title = "Legenda"
    legenda.showTitle = True
    legenda.columnCount = 2
    legenda.fittingStrategy = "AdjustColumnsAndFont"
    legenda.syncNewLayer = False
    legenda.syncLayerOrder = True
    legenda.syncLayerVisibility = True

    nomes_validos = {
        f"{codigo} - {descricao} ({contagens.get(codigo, 0)})"
        for codigo, (descricao, _) in STATUS_LEGENDA.items()
        if int(contagens.get(codigo, 0) or 0) > 0
    }
    if bairro:
        nomes_validos.add(f"Bairro {bairro}")
    else:
        nomes_validos.add("Bairro")
    nomes_validos.add("Quadras")
    for item in list(legenda.items):
        try:
            nome_item = str(item.name or "").strip()
            nome_camada = str(getattr(item, "layerName", "") or "").strip()
            if nome_item not in nomes_validos and nome_camada not in nomes_validos:
                legenda.removeItem(item)
                continue
            item.patchWidth = 10
            item.patchHeight = 7
            item.showFeatureCount = False
            item.showVisibleFeatures = False
        except Exception:
            pass

    try:
        legenda.elementPositionX = 257.0
        legenda.elementPositionY = 284.0
        legenda.elementWidth = 152.0
        legenda.elementHeight = 35.0
    except Exception:
        pass
    return legenda


def _contar_beneficiarios(shp_lotes):
    campo_status = _campo_existente(shp_lotes, ["status"])
    if not campo_status:
        return 0
    total = 0
    with arcpy.da.SearchCursor(shp_lotes, [campo_status]) as cursor:
        for row in cursor:
            try:
                if int(row[0] or 0) in (1, 4):
                    total += 1
            except Exception:
                pass
    return total


def _valor_quadra_para_ordem(valor):
    texto = str(valor or "").strip()
    if texto.isdigit():
        return (0, int(texto), "")
    return (1, texto.lower(), texto)


def _resumo_quadras(shp_lotes, quadras_fc=None):
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    if not campo_quadra:
        raise ValueError("Campo 'quadra' nao encontrado no shapefile de lotes.")

    sr_utm = arcpy.SpatialReference(31983)
    resumo = {}
    with arcpy.da.SearchCursor(shp_lotes, [campo_quadra]) as cursor:
        for row in cursor:
            quadra = row[0]
            quadra = str(quadra or "").strip() or "Sem quadra"
            if quadra not in resumo:
                resumo[quadra] = {"quadra": quadra, "area": 0.0, "lotes": 0}
            resumo[quadra]["lotes"] += 1

    fonte_area = quadras_fc if _dataset_tem_features(quadras_fc) else shp_lotes
    campo_quadra_area = _campo_existente(fonte_area, [campo_quadra, "quadra"])
    with arcpy.da.SearchCursor(fonte_area, [campo_quadra_area, "SHAPE@"]) as cursor:
        for quadra, geom in cursor:
            quadra = str(quadra or "").strip() or "Sem quadra"
            if quadra not in resumo:
                resumo[quadra] = {"quadra": quadra, "area": 0.0, "lotes": 0}
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            resumo[quadra]["area"] += float(getattr(geom, "area", 0) or 0)

    return sorted(resumo.values(), key=lambda item: _valor_quadra_para_ordem(item["quadra"]))


def _criar_gdb_temporaria(pasta, nome="dados_prancha_geral.gdb"):
    gdb = Path(pasta) / nome
    if not gdb.exists():
        arcpy.management.CreateFileGDB(str(gdb.parent), gdb.name)
    return gdb


def _dissolver_quadras(shp_lotes, pasta):
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    if not campo_quadra:
        raise ValueError("Campo 'quadra' nao encontrado no shapefile de lotes.")

    gdb = _criar_gdb_temporaria(pasta)
    saida = str(gdb / "quadras_dissolvidas")
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    arcpy.management.Dissolve(
        in_features=shp_lotes,
        out_feature_class=saida,
        dissolve_field=[campo_quadra],
        multi_part="MULTI_PART",
        unsplit_lines="DISSOLVE_LINES",
    )
    return saida, campo_quadra


def _criar_tabela_resumo_quadras(pasta, resumo):
    gdb = _criar_gdb_temporaria(pasta)
    tabela = str(gdb / "resumo_quadras")
    if arcpy.Exists(tabela):
        arcpy.management.Delete(tabela)
    arcpy.management.CreateTable(str(gdb), "resumo_quadras")
    arcpy.management.AddField(tabela, "Quadra", "TEXT", field_length=30, field_alias="Quadra")
    arcpy.management.AddField(tabela, "Area_m2", "TEXT", field_length=30, field_alias="Area (m2)")
    arcpy.management.AddField(tabela, "Lotes", "LONG", field_alias="Qtd. lotes")

    total_area = 0.0
    total_lotes = 0
    with arcpy.da.InsertCursor(tabela, ["Quadra", "Area_m2", "Lotes"]) as cursor:
        for item in resumo:
            area = float(item["area"] or 0)
            lotes = int(item["lotes"] or 0)
            total_area += area
            total_lotes += lotes
            cursor.insertRow([str(item["quadra"]), decimal_texto(area, 2), lotes])
        cursor.insertRow(["TOTAL", decimal_texto(total_area, 2), total_lotes])
    return tabela


def _configurar_quadro_tabela_quadras(layout, aprx_map, tabela_resumo):
    tabela_mp = arcpy.mp.Table(tabela_resumo)
    aprx_map.addTable(tabela_mp)
    tabelas = aprx_map.listTables()
    tabela_layout = tabelas[-1] if tabelas else tabela_mp

    frames = layout.listElements("TABLEFRAME_ELEMENT", "tabela_dados")
    if not frames:
        map_frames = layout.listElements("MAPFRAME_ELEMENT", "MAP_FRAME")
        if not map_frames:
            return None
        frames = [
            layout.createTableFrameElement(
                arcpy.Point(257.0, 284.0),
                map_frames[0],
                tabela_layout,
                "quadro_resumo_quadras",
            )
        ]

    frame = frames[0]
    frame.table = tabela_layout
    frame.visible = True
    try:
        frame.elementPositionX = 257.0
        frame.elementPositionY = 284.0
        frame.elementWidth = 152.0
        frame.elementHeight = 140.0
    except Exception:
        pass
    return frame


def _configurar_rotulos_quadras(layer, campo_quadra):
    try:
        layer.showLabels = True
        for label_class in layer.listLabelClasses():
            label_class.expression = f"'Q' + Text($feature.{campo_quadra})"
            try:
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            label_class.visible = True

        cim = layer.getDefinition("V3")
        for label_class in getattr(cim, "labelClasses", []):
            label_class.visible = True
            try:
                label_class.expression = f"'Q' + Text($feature.{campo_quadra})"
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            text_symbol = getattr(label_class, "textSymbol", None)
            if text_symbol is not None:
                _configurar_texto_quadra(text_symbol, 6.8)
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel configurar rotulos das quadras: {exc}")


def _aplicar_simbolo_quadra_geral(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            symbol.color = {"RGB": [231, 245, 232, 55]}
            try:
                symbol.outlineColor = {"RGB": [20, 92, 45, 100]}
                symbol.outlineWidth = 1.4
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia das quadras: {exc}")


def _aplicar_simbologia_quadras(layer, simbologia_quadras=None):
    if _aplicar_simbologia_arquivo(layer, simbologia_quadras):
        return True
    _aplicar_simbolo_quadra_geral(layer)
    return False


def _aplicar_simbolo_frente_lote(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            try:
                symbol.color = {"RGB": [255, 0, 180, 100]}
            except Exception:
                pass
            try:
                symbol.width = 2.0
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia das frentes dos lotes: {exc}")


def _iterar_symbol_layers_cim(cim):
    visitados = set()

    def visitar(objeto, profundidade=0):
        if objeto is None or profundidade > 8:
            return
        obj_id = id(objeto)
        if obj_id in visitados:
            return
        visitados.add(obj_id)
        for prop in ["symbolLayers", "layers"]:
            try:
                for item in getattr(objeto, prop, []) or []:
                    yield item
                    yield from visitar(item, profundidade + 1)
            except Exception:
                pass
        for prop in ["renderer", "symbol", "symbolReference"]:
            try:
                if hasattr(objeto, prop):
                    yield from visitar(getattr(objeto, prop), profundidade + 1)
            except Exception:
                pass

    yield from visitar(cim)


def _aplicar_simbolo_vertices_limite(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            for nome_galeria in ["Circle 1", "Circle", "Circle 3"]:
                try:
                    symbol.applySymbolFromGallery(nome_galeria)
                    break
                except Exception:
                    pass
            try:
                symbol.color = {"RGB": [255, 255, 255, 0]}
            except Exception:
                pass
            try:
                symbol.outlineColor = {"RGB": [20, 20, 20, 100]}
                symbol.outlineWidth = 1.1
            except Exception:
                pass
            try:
                symbol.size = 4.8
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
        cim = layer.getDefinition("V3")
        for symbol_layer in _iterar_symbol_layers_cim(cim):
            try:
                if hasattr(symbol_layer, "color"):
                    symbol_layer.color.values = [255, 255, 255, 0]
            except Exception:
                pass
            try:
                if hasattr(symbol_layer, "outlineColor"):
                    symbol_layer.outlineColor.values = [20, 20, 20, 100]
            except Exception:
                pass
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia dos vertices do limite: {exc}")


def _aplicar_simbolo_marcacao_frente(layer):
    try:
        sym = layer.symbology
        if hasattr(sym, "renderer") and hasattr(sym.renderer, "symbol"):
            symbol = sym.renderer.symbol
            for nome_galeria in ["Triangle 1", "Triangle", "Triangle 3"]:
                try:
                    symbol.applySymbolFromGallery(nome_galeria)
                    break
                except Exception:
                    pass
            try:
                symbol.color = {"RGB": [95, 95, 95, 100]}
            except Exception:
                pass
            try:
                symbol.size = 3.2
            except Exception:
                pass
            sym.renderer.symbol = symbol
            layer.symbology = sym
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel aplicar simbologia da marcacao da frente: {exc}")


def _configurar_rotulos_numero_lote(layer, campo_lote):
    try:
        layer.showLabels = True
        for label_class in layer.listLabelClasses():
            label_class.expression = f"Text($feature.{campo_lote})"
            try:
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            label_class.visible = True

        cim = layer.getDefinition("V3")
        for label_class in getattr(cim, "labelClasses", []):
            label_class.visible = True
            try:
                label_class.expression = f"Text($feature.{campo_lote})"
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            text_symbol = getattr(label_class, "textSymbol", None)
            if text_symbol is not None:
                _configurar_texto_lote(text_symbol, 4.1)
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel configurar numeros dos lotes: {exc}")


def _configurar_rotulos_vertices(layer):
    try:
        campo_nome = _campo_existente(layer, ["vertice"])
        if not campo_nome:
            return
        layer.showLabels = True
        for label_class in layer.listLabelClasses():
            label_class.expression = f"$feature.{campo_nome}"
            try:
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            label_class.visible = True

        cim = layer.getDefinition("V3")
        for label_class in getattr(cim, "labelClasses", []):
            label_class.visible = True
            try:
                label_class.expression = f"$feature.{campo_nome}"
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            text_symbol = getattr(label_class, "textSymbol", None)
            if text_symbol is not None:
                _ajustar_text_symbol(text_symbol, 3.6)
        layer.setDefinition(cim)
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel configurar rotulos dos vertices do limite: {exc}")


def _criar_vertices_limite_bairro(shp_bairro, pasta):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        return None
    sr_utm = arcpy.SpatialReference(31983)
    gdb = _criar_gdb_temporaria(pasta)
    saida = str(gdb / "vertices_limite_bairro")
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    arcpy.management.CreateFeatureclass(
        str(gdb),
        "vertices_limite_bairro",
        "POINT",
        spatial_reference=sr_utm,
    )
    arcpy.management.AddField(saida, "vertice", "TEXT", field_length=20)
    arcpy.management.AddField(saida, "ordem", "LONG")

    ordem = 1
    with arcpy.da.InsertCursor(saida, ["vertice", "ordem", "SHAPE@"]) as insert:
        with arcpy.da.SearchCursor(shp_bairro, ["SHAPE@"]) as cursor:
            for row in cursor:
                geom = row[0]
                if not geom:
                    continue
                try:
                    geom = geom.projectAs(sr_utm)
                except Exception:
                    pass
                for parte in geom:
                    pontos = [p for p in parte if p]
                    if len(pontos) < 2:
                        continue
                    if abs(pontos[0].X - pontos[-1].X) < 0.001 and abs(pontos[0].Y - pontos[-1].Y) < 0.001:
                        pontos = pontos[:-1]
                    for ponto in pontos:
                        insert.insertRow([
                            f"P-{ordem:02d}",
                            ordem,
                            arcpy.PointGeometry(arcpy.Point(ponto.X, ponto.Y), sr_utm),
                        ])
                        ordem += 1
    arcpy.AddMessage(f"Vertices do limite do bairro criados: {ordem - 1}")
    return saida


def _segmentos_anel(geom):
    for parte in geom:
        pontos = [p for p in parte if p]
        if len(pontos) < 2:
            continue
        for idx in range(len(pontos) - 1):
            yield pontos[idx], pontos[idx + 1]
        primeiro = pontos[0]
        ultimo = pontos[-1]
        if abs(primeiro.X - ultimo.X) > 0.001 or abs(primeiro.Y - ultimo.Y) > 0.001:
            yield ultimo, primeiro


def _distancia_segmento_eixos(ponto_a, ponto_b, eixos, sr):
    midpoint = arcpy.PointGeometry(
        arcpy.Point((ponto_a.X + ponto_b.X) / 2, (ponto_a.Y + ponto_b.Y) / 2),
        sr,
    )
    melhor = None
    for _, eixo in eixos:
        try:
            distancia = midpoint.distanceTo(eixo)
        except Exception:
            continue
        if melhor is None or distancia < melhor:
            melhor = distancia
    return melhor


def _carregar_pontos_frente(shp_frente_lotes):
    if not shp_frente_lotes or not arcpy.Exists(shp_frente_lotes):
        return []
    sr_utm = arcpy.SpatialReference(31983)
    campo_quadra = _campo_existente(shp_frente_lotes, ["quadra"])
    campo_lote = _campo_existente(shp_frente_lotes, ["lote"])
    campo_coletivo = _campo_existente(shp_frente_lotes, ["n_coletivo", "coletivo", "reurb"])
    campos = ["OID@", "SHAPE@"]
    campos.extend([campo for campo in [campo_quadra, campo_lote, campo_coletivo] if campo])
    pontos = []
    with arcpy.da.SearchCursor(shp_frente_lotes, campos) as cursor:
        for row in cursor:
            oid = row[0]
            geom = row[1]
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            valores = {}
            idx = 2
            if campo_quadra:
                valores["quadra"] = str(row[idx] or "").strip()
                idx += 1
            if campo_lote:
                valores["lote"] = str(row[idx] or "").strip()
                idx += 1
            if campo_coletivo:
                valores["n_coletivo"] = str(row[idx] or "").strip()
            pontos.append({
                "oid": oid,
                "geom": geom,
                "quadra": valores.get("quadra", ""),
                "lote": valores.get("lote", ""),
                "n_coletivo": valores.get("n_coletivo", ""),
            })
    return pontos


def _pontos_frente_do_lote(geom_lote, pontos_frente, quadra="", lote="", n_coletivo="", tolerancia=8):
    quadra = str(quadra or "").strip()
    lote = str(lote or "").strip()
    n_coletivo = str(n_coletivo or "").strip()
    por_atributo = []
    for ponto in pontos_frente:
        if ponto.get("quadra") and ponto.get("quadra") != quadra:
            continue
        if ponto.get("lote") and ponto.get("lote") != lote:
            continue
        if ponto.get("n_coletivo") and ponto.get("n_coletivo") != n_coletivo:
            continue
        if ponto.get("quadra") or ponto.get("lote") or ponto.get("n_coletivo"):
            por_atributo.append((ponto["oid"], ponto["geom"], 0))
    if por_atributo:
        return por_atributo

    candidatos = []
    for ponto in pontos_frente:
        geom_ponto = ponto["geom"]
        try:
            distancia = geom_ponto.distanceTo(geom_lote)
        except Exception:
            continue
        if distancia <= tolerancia:
            candidatos.append((ponto["oid"], geom_ponto, distancia))
    if candidatos:
        return candidatos

    melhor = None
    for ponto in pontos_frente:
        geom_ponto = ponto["geom"]
        try:
            distancia = geom_ponto.distanceTo(geom_lote)
        except Exception:
            continue
        if melhor is None or distancia < melhor[2]:
            melhor = (ponto["oid"], geom_ponto, distancia)
    if melhor and melhor[2] <= 35:
        return [melhor]
    return []


def _distancia_segmento_pontos(ponto_a, ponto_b, pontos, sr):
    linha = arcpy.Polyline(arcpy.Array([ponto_a, ponto_b]), sr)
    melhor = None
    for _, ponto, _ in pontos:
        try:
            distancia = ponto.distanceTo(linha)
        except Exception:
            continue
        if melhor is None or distancia < melhor:
            melhor = distancia
    return melhor


def _criar_frentes_lotes(shp_lotes, eixo_viario, pasta, tolerancia=35, shp_frente_lotes=None):
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        arcpy.AddWarning("Eixo viario nao encontrado. As frentes serao inferidas pelo maior segmento de cada lote.")
    sr_utm = arcpy.SpatialReference(31983)
    eixos = _carregar_eixos(eixo_viario)
    pontos_frente = _carregar_pontos_frente(shp_frente_lotes)
    if pontos_frente:
        arcpy.AddMessage(f"Pontos de frente de lote carregados: {len(pontos_frente)}")
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    campo_lote = _campo_existente(shp_lotes, ["lote"])
    campo_coletivo = _campo_existente(shp_lotes, ["n_coletivo", "numero", "processo"])
    gdb = _criar_gdb_temporaria(pasta)
    saida = str(gdb / "frentes_lotes")
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)

    arcpy.management.CreateFeatureclass(
        str(gdb),
        "frentes_lotes",
        "POLYLINE",
        spatial_reference=sr_utm,
    )
    arcpy.management.AddField(saida, "quadra", "TEXT", field_length=30)
    arcpy.management.AddField(saida, "lote", "TEXT", field_length=50)
    arcpy.management.AddField(saida, "dist_rua", "DOUBLE")

    campos = [campo for campo in [campo_quadra, campo_lote, campo_coletivo] if campo] + ["SHAPE@"]
    total = 0
    with arcpy.da.InsertCursor(saida, ["quadra", "lote", "dist_rua", "SHAPE@"]) as insert:
        with arcpy.da.SearchCursor(shp_lotes, campos) as cursor:
            for row in cursor:
                valores = {}
                idx = 0
                if campo_quadra:
                    valores["quadra"] = row[idx]
                    idx += 1
                if campo_lote:
                    valores["lote"] = row[idx]
                    idx += 1
                if campo_coletivo:
                    valores["n_coletivo"] = row[idx]
                    idx += 1
                geom = row[idx]
                quadra = valores.get("quadra", "")
                lote = valores.get("lote", "")
                n_coletivo = valores.get("n_coletivo", "")
                if not geom:
                    continue
                try:
                    geom_utm = geom.projectAs(sr_utm)
                except Exception:
                    geom_utm = geom

                pontos_lote = _pontos_frente_do_lote(
                    geom_utm,
                    pontos_frente,
                    quadra=quadra,
                    lote=lote,
                    n_coletivo=n_coletivo,
                ) if pontos_frente else []
                melhor_segmento = None
                melhor_distancia = None
                maior_segmento = None
                maior_comprimento = 0
                for ponto_a, ponto_b in _segmentos_anel(geom_utm):
                    comprimento = math.hypot(ponto_b.X - ponto_a.X, ponto_b.Y - ponto_a.Y)
                    if comprimento > maior_comprimento:
                        maior_comprimento = comprimento
                        maior_segmento = (ponto_a, ponto_b)
                    if pontos_lote:
                        distancia = _distancia_segmento_pontos(ponto_a, ponto_b, pontos_lote, sr_utm)
                    else:
                        distancia = _distancia_segmento_eixos(ponto_a, ponto_b, eixos, sr_utm) if eixos else None
                    if distancia is not None and (melhor_distancia is None or distancia < melhor_distancia):
                        melhor_distancia = distancia
                        melhor_segmento = (ponto_a, ponto_b)

                usar_segmento = melhor_segmento if (pontos_lote and melhor_segmento) or (melhor_segmento and melhor_distancia <= tolerancia) else maior_segmento
                if not usar_segmento:
                    continue
                array = arcpy.Array([usar_segmento[0], usar_segmento[1]])
                linha = arcpy.Polyline(array, sr_utm)
                insert.insertRow([str(quadra or ""), str(lote or ""), melhor_distancia or 0, linha])
                total += 1

    arcpy.AddMessage(f"Frentes de lote criadas: {total}")
    return saida


def _valor_unico_campo(dataset, candidatos):
    campo = _campo_existente(dataset, candidatos)
    if not campo:
        return ""
    try:
        with arcpy.da.SearchCursor(dataset, [campo]) as cursor:
            for row in cursor:
                if row[0]:
                    return str(row[0]).strip()
    except Exception:
        pass
    return ""


def _aplicar_filtro_marcacao_frente(layer, shp_lotes):
    n_coletivo = _valor_unico_campo(shp_lotes, ["n_coletivo", "numero", "processo"])
    campo_coletivo = _campo_existente(layer, ["n_coletivo", "coletivo", "reurb"])
    if not n_coletivo or not campo_coletivo:
        return
    try:
        delimitado = arcpy.AddFieldDelimiters("", campo_coletivo)
        valor = n_coletivo.replace("'", "''")
        layer.definitionQuery = f"{delimitado} = '{valor}'"
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel filtrar marcacoes de frente: {exc}")


def _adicionar_camadas_planta_geral(aprx_map, shp_lotes, shp_bairro, bairro, pasta, eixo_viario=None, shp_frente_lotes=None, shp_quadras=None):
    if shp_bairro and arcpy.Exists(shp_bairro):
        bairro_layer = _adicionar_camada_bairro(aprx_map, shp_bairro, bairro)
        if bairro_layer:
            bairro_layer.name = "Limite do bairro"
            _desativar_rotulos(bairro_layer)

    lotes_layer = aprx_map.addDataFromPath(shp_lotes)
    lotes_layer.name = "Lotes"
    _aplicar_simbolo_contorno(lotes_layer, [45, 95, 210, 85], 0.28)
    _desativar_rotulos(lotes_layer)

    campo_lote_rotulo = _campo_existente(shp_lotes, ["lote"])
    if campo_lote_rotulo:
        rotulos_lotes = aprx_map.addDataFromPath(shp_lotes)
        rotulos_lotes.name = "Numero dos lotes"
        _ocultar_simbolo(rotulos_lotes)
        _configurar_rotulos_numero_lote(rotulos_lotes, campo_lote_rotulo)

    if _dataset_tem_features(shp_quadras):
        quadras_fc = shp_quadras
        campo_quadra = _campo_existente(shp_quadras, ["quadra"])
    else:
        quadras_fc, campo_quadra = _dissolver_quadras(shp_lotes, pasta)
    quadras_layer = aprx_map.addDataFromPath(quadras_fc)
    quadras_layer.name = "Quadras"
    _aplicar_simbolo_quadra_geral(quadras_layer)
    if campo_quadra:
        _configurar_rotulos_quadras(quadras_layer, campo_quadra)

    vertices_fc = _criar_vertices_limite_bairro(shp_bairro, pasta)
    if vertices_fc:
        vertices_layer = aprx_map.addDataFromPath(vertices_fc)
        vertices_layer.name = "Vertices do limite"
        _aplicar_simbolo_vertices_limite(vertices_layer)
        _configurar_rotulos_vertices(vertices_layer)
    return quadras_fc


def _criar_legenda_planta_geral_bairro(layout, map_frame):
    _remover_legendas(layout)
    try:
        legenda = layout.createMapSurroundElement(
            arcpy.Point(314.0, 284.0),
            "LEGEND",
            map_frame,
            None,
            "LEGENDA_PLANTA_GERAL_BAIRRO",
        )
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel criar legenda da planta geral: {exc}")
        return None

    try:
        legenda.setAnchor("TOP_LEFT_CORNER")
    except Exception:
        pass
    legenda.title = "Legenda"
    legenda.showTitle = True
    legenda.columnCount = 1
    legenda.fittingStrategy = "AdjustFrame"
    legenda.syncNewLayer = False
    legenda.syncLayerOrder = True
    legenda.syncLayerVisibility = True

    nomes_validos = {
        "Limite do bairro",
        "Lotes",
        "Quadras",
        "Vertices do limite",
    }
    for item in list(legenda.items):
        try:
            nome_item = str(item.name or "").strip()
            if "marcacao" in nome_item.lower() or "marcação" in nome_item.lower() or nome_item not in nomes_validos:
                legenda.removeItem(item)
                continue
            item.showFeatureCount = False
            item.showVisibleFeatures = False
            item.patchWidth = 9
            item.patchHeight = 5
        except Exception:
            pass

    try:
        legenda.elementPositionX = 314.0
        legenda.elementPositionY = 284.0
        legenda.elementWidth = 92.0
        legenda.elementHeight = 42.0
    except Exception:
        pass
    return legenda


def _remover_legendas(layout):
    for legenda in list(layout.listElements("LEGEND_ELEMENT")):
        try:
            layout.deleteElement(legenda)
        except Exception:
            try:
                legenda.visible = False
            except Exception:
                pass


def _formatar_linha_quadra(item):
    return "{:<8} {:>13} {:>8}".format(
        str(item["quadra"])[:8],
        decimal_texto(item["area"], 2),
        str(item["lotes"]),
    )


def _quebrar_resumo_em_colunas(resumo, linhas_por_coluna=29):
    colunas = []
    for indice in range(0, len(resumo), linhas_por_coluna):
        colunas.append(resumo[indice:indice + linhas_por_coluna])
    return colunas or [[]]


def _criar_quadro_resumo_quadras(layout, resumo, total_area, total_lotes):
    cabecalho = "Quadra    Area (m2)    Lotes"
    colunas = _quebrar_resumo_em_colunas(resumo)
    posicoes = [(258.0, 276.0), (334.0, 276.0)]
    for indice, coluna in enumerate(colunas[:2]):
        linhas = [cabecalho] + [_formatar_linha_quadra(item) for item in coluna]
        if indice == 0:
            linhas.extend([
                "",
                "Total    {} {}".format(decimal_texto(total_area, 2).rjust(13), str(total_lotes).rjust(8)),
            ])
        x, y = posicoes[indice]
        _texto_existente(
            layout,
            f"quadro_resumo_quadras_{indice + 1}",
            "\n".join(linhas),
            x=x,
            y=y,
            tamanho=5.4,
            largura=72.0,
        )

    for indice in range(len(colunas), 2):
        _texto_existente(
            layout,
            f"quadro_resumo_quadras_{indice + 1}",
            "",
            x=posicoes[indice][0],
            y=posicoes[indice][1],
            tamanho=5.4,
            largura=72.0,
        )


def _atualizar_textos_planta_geral(
    layout,
    numero,
    municipio,
    bairro,
    escala,
    resumo_quadras,
    area_bairro=None,
    perimetro_bairro=None,
    responsavel_tecnico=None,
):
    total_quadras = len(resumo_quadras)
    total_lotes = sum(item["lotes"] for item in resumo_quadras)
    total_area_quadras = sum(item["area"] for item in resumo_quadras)
    hoje = datetime.now().strftime("%d/%m/%Y")
    area_bairro_texto = decimal_texto(area_bairro, 2) if area_bairro else ""
    perimetro_bairro_texto = decimal_texto(perimetro_bairro, 2) if perimetro_bairro else ""
    responsavel_tecnico = responsavel_tecnico or {}

    substituicoes = {
        "{bairro}": bairro,
        "{municipio}": municipio,
        "{area}": area_bairro_texto,
        "{matricula}": numero,
        "{folha}": bairro,
        "{perimetro}": perimetro_bairro_texto,
        "{data}": hoje,
        "{fusoutm}": "23S",
        "{responsavel_tecnico}": responsavel_tecnico.get("nome", ""),
        "{funcao}": responsavel_tecnico.get("formacao", ""),
        "{n_crea_cau}": responsavel_tecnico.get("registro", ""),
    }

    for elemento in layout.listElements("TEXT_ELEMENT"):
        try:
            texto = elemento.text
            if str(texto).strip() == "{bairro}":
                elemento.text = ""
                continue
            texto = texto.replace("Matrícula:", "Processo:")
            texto = texto.replace("Matricula:", "Processo:")
            texto = texto.replace("Folha:", "Bairro:")
            elemento.text = texto
            for chave, valor in substituicoes.items():
                if chave in elemento.text or chave == elemento.name:
                    elemento.text = elemento.text.replace(chave, valor)
            if "PLANTA LOTEAMENTO" in elemento.text or "Planta Perimetro" in elemento.text or "Planta Perímetro" in elemento.text:
                elemento.text = "PLANTA GERAL DO LOTEAMENTO"
        except Exception:
            pass

    _texto_existente(
        layout,
        "titulo_prancha_loteamento",
        "PLANTA GERAL DO LOTEAMENTO",
        x=13.1,
        y=27.35,
        tamanho=12,
        largura=18.0,
    )
    _texto_existente(
        layout,
        "subtitulo_prancha_loteamento",
        "Quadro resumo: quadra, area e quantidade de lotes",
        x=13.1,
        y=26.95,
        tamanho=7,
        largura=18.0,
    )
    _texto_existente(
        layout,
        "carimbo_prancha_loteamento",
        (
            "Dados da Prancha\n"
            f"Municipio: {municipio}\n"
            f"Bairro: {bairro}\n"
            f"Processo: {numero}\n"
            f"Area do bairro (m2): {area_bairro_texto}\n"
            f"Perimetro do bairro (m): {perimetro_bairro_texto}\n"
            f"Total de quadras: {total_quadras}\n"
            f"Total de lotes: {total_lotes}\n"
            f"Area somada das quadras (m2): {decimal_texto(total_area_quadras, 2)}\n"
            "Sistema: SIRGAS 2000 / UTM 23S\n"
            f"Escala aproximada: 1:{escala}"
        ),
        x=21.8,
        y=13.2,
        tamanho=6.0,
        largura=14.8,
    )
    _texto_existente(
        layout,
        "titulo_planta_situacao_loteamento",
        "Quadro de Quadras:",
        x=257.0,
        y=284.5,
        tamanho=7.2,
        largura=80.0,
    )
    _criar_quadro_resumo_quadras(layout, resumo_quadras, total_area_quadras, total_lotes)


def _gerar_lista_pdf_se_possivel(shp_lotes, numero, municipio, bairro, pasta):
    try:
        from gerar_prancha_loteamento import _carregar_lotes, _gerar_lista_beneficiarios
        nome_base = f"PRANCHA_02_LISTA_DE_BENEFICIARIOS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}.pdf"
        lista_pdf = pasta / nome_base
        lotes = _carregar_lotes(shp_lotes)
        _gerar_lista_beneficiarios(lista_pdf, lotes, municipio, bairro, numero)
        return str(lista_pdf)
    except Exception as exc:
        arcpy.AddWarning(f"Lista de beneficiarios nao foi gerada pelo Python do ArcGIS: {exc}")

    python_externo = _python_externo()
    if not python_externo:
        arcpy.AddWarning("Python externo com reportlab nao encontrado para gerar a lista de beneficiarios.")
        return None

    try:
        nome_base = f"PRANCHA_02_LISTA_DE_BENEFICIARIOS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}.pdf"
        lista_pdf = pasta / nome_base
        codigo = (
            "import sys\n"
            "from pathlib import Path\n"
            "from gerar_prancha_loteamento import _carregar_lotes, _gerar_lista_beneficiarios\n"
            "shp, numero, municipio, bairro, saida = sys.argv[1:6]\n"
            "_gerar_lista_beneficiarios(Path(saida), _carregar_lotes(shp), municipio, bairro, numero)\n"
        )
        resultado = subprocess.run(
            [python_externo, "-c", codigo, str(shp_lotes), str(numero), str(municipio), str(bairro), str(lista_pdf)],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent),
            env=_ambiente_python_externo(),
        )
        if lista_pdf.exists():
            arcpy.AddMessage(f"Lista de beneficiarios gerada pelo Python externo: {lista_pdf}")
            return str(lista_pdf)
        detalhe = (resultado.stderr or resultado.stdout or "processo concluiu sem criar o PDF").strip()
        arcpy.AddWarning(f"Python externo nao criou a lista de beneficiarios: {detalhe}")
    except subprocess.CalledProcessError as exc:
        detalhe = (exc.stderr or exc.stdout or str(exc)).strip()
        arcpy.AddWarning(f"Lista de beneficiarios nao foi gerada pelo Python externo: {detalhe}")
    except Exception as exc:
        arcpy.AddWarning(f"Lista de beneficiarios nao foi gerada pelo Python externo: {exc}")
    return None


def _anexar_pdfs(planta_pdf, lista_pdf, saida_pdf):
    if not lista_pdf or not os.path.exists(lista_pdf):
        shutil.copy2(planta_pdf, saida_pdf)
        return saida_pdf

    try:
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        for caminho in [planta_pdf, lista_pdf]:
            reader = PdfReader(caminho)
            for page in reader.pages:
                writer.add_page(page)
        with open(saida_pdf, "wb") as arquivo:
            writer.write(arquivo)
        return saida_pdf
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel anexar lista ao PDF da planta pelo Python do ArcGIS: {exc}")

    python_externo = _python_externo()
    if python_externo:
        try:
            codigo = (
                "from pypdf import PdfReader, PdfWriter; "
                "import sys; "
                "w=PdfWriter(); "
                "\nfor p in sys.argv[1:3]:\n"
                "    r=PdfReader(p)\n"
                "    [w.add_page(pg) for pg in r.pages]\n"
                "open(sys.argv[3],'wb').write(b'')\n"
                "with open(sys.argv[3],'wb') as f: w.write(f)\n"
            )
            subprocess.run(
                [python_externo, "-c", codigo, planta_pdf, lista_pdf, saida_pdf],
                check=True,
                capture_output=True,
                text=True,
                env=_ambiente_python_externo(),
            )
            return saida_pdf
        except Exception as exc:
            arcpy.AddWarning(f"Nao foi possivel anexar lista pelo Python externo: {exc}")

    shutil.copy2(planta_pdf, saida_pdf)
    return saida_pdf


def _python_externo():
    candidatos = [
        Path(r"C:\Users\gusta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    ]
    if os.environ.get("CODEX_PYTHON"):
        candidatos.append(Path(os.environ["CODEX_PYTHON"]))
    for caminho in candidatos:
        if caminho and caminho.exists() and caminho.is_file():
            return str(caminho)
    return None


def _ambiente_python_externo():
    env = os.environ.copy()
    for chave in ("PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__"):
        env.pop(chave, None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _lista_entrada(valor):
    if not valor:
        return []
    if isinstance(valor, (list, tuple)):
        return [str(item) for item in valor if item]
    return [str(valor)]


def _shps_por_padrao(padrao):
    pasta_shp = Path(r"C:\REURB\SHP")
    return [str(caminho) for caminho in sorted(pasta_shp.glob(padrao)) if caminho.suffix.lower() == ".shp"]


def _nome_bairro_dataset(dataset):
    campo_nome = _campo_existente(dataset, ["nome", "bairro"])
    if campo_nome:
        try:
            with arcpy.da.SearchCursor(dataset, [campo_nome]) as cursor:
                for row in cursor:
                    if row[0]:
                        return str(row[0]).strip().title()
        except Exception:
            pass
    nome = Path(dataset).stem
    nome = re.sub(r"^(bairro|lotes)_", "", nome, flags=re.IGNORECASE)
    nome = re.sub(r"_[0-9]{9}_[0-9]{4}$", "", nome)
    return nome.replace("_", " ").title()


def _inferir_bairro_lotes(dataset):
    campo_bairro = _campo_existente(dataset, ["bairro", "nome_bairro", "nucleo"])
    if campo_bairro:
        try:
            with arcpy.da.SearchCursor(dataset, [campo_bairro]) as cursor:
                for row in cursor:
                    if row[0]:
                        return str(row[0]).strip().title()
        except Exception:
            pass
    return _nome_bairro_dataset(dataset)


def _copiar_com_bairro(dataset, saida, bairro):
    if arcpy.Exists(saida):
        arcpy.management.Delete(saida)
    arcpy.management.CopyFeatures(dataset, saida)
    campo_bairro = _campo_existente(saida, ["bairro", "nome_bairro", "nucleo"])
    if not campo_bairro:
        arcpy.management.AddField(saida, "bairro", "TEXT", field_length=120)
        campo_bairro = "bairro"
    with arcpy.da.UpdateCursor(saida, [campo_bairro]) as cursor:
        for row in cursor:
            row[0] = bairro
            cursor.updateRow(row)
    return saida


def _preparar_dados_municipio(shps_lotes, shps_bairros, pasta):
    shps_lotes = _lista_entrada(shps_lotes) or _shps_por_padrao("lotes_*.shp")
    shps_bairros = _lista_entrada(shps_bairros) or _shps_por_padrao("bairro_*.shp")
    if not shps_lotes:
        raise ValueError("Nenhum shapefile de lotes encontrado para a planta geral municipal.")
    if not shps_bairros:
        raise ValueError("Nenhum shapefile de bairro/perimetro encontrado para a planta geral municipal.")

    gdb = _criar_gdb_temporaria(pasta, "dados_prancha_municipal.gdb")
    lotes_temp = []
    bairros_temp = []
    bairros_nomes = []

    for indice, shp in enumerate(shps_lotes, start=1):
        bairro = _inferir_bairro_lotes(shp)
        bairros_nomes.append(bairro)
        lotes_temp.append(_copiar_com_bairro(shp, str(gdb / f"lotes_{indice}"), bairro))

    for indice, shp in enumerate(shps_bairros, start=1):
        bairro = _nome_bairro_dataset(shp)
        bairros_nomes.append(bairro)
        bairros_temp.append(_copiar_com_bairro(shp, str(gdb / f"bairro_{indice}"), bairro))

    lotes_municipio = str(gdb / "lotes_municipio")
    bairros_municipio = str(gdb / "bairros_municipio")
    perimetro_municipio = str(gdb / "perimetro_reurb_municipio")
    for caminho in [lotes_municipio, bairros_municipio, perimetro_municipio]:
        if arcpy.Exists(caminho):
            arcpy.management.Delete(caminho)

    arcpy.management.Merge(lotes_temp, lotes_municipio)
    arcpy.management.Merge(bairros_temp, bairros_municipio)
    arcpy.management.Dissolve(
        in_features=bairros_municipio,
        out_feature_class=perimetro_municipio,
        multi_part="MULTI_PART",
        unsplit_lines="DISSOLVE_LINES",
    )
    bairros_nomes = sorted({nome for nome in bairros_nomes if nome}, key=lambda item: item.lower())
    return lotes_municipio, bairros_municipio, perimetro_municipio, bairros_nomes


def _resumo_quadras_municipio(shp_lotes, pasta):
    campo_bairro = _campo_existente(shp_lotes, ["bairro", "nome_bairro", "nucleo"])
    campo_quadra = _campo_existente(shp_lotes, ["quadra"])
    if not campo_bairro or not campo_quadra:
        raise ValueError("Campos 'bairro' e/ou 'quadra' nao encontrados nos lotes municipais.")

    gdb = _criar_gdb_temporaria(pasta, "dados_prancha_municipal.gdb")
    quadras_fc = str(gdb / "quadras_municipio")
    if arcpy.Exists(quadras_fc):
        arcpy.management.Delete(quadras_fc)
    arcpy.management.Dissolve(
        in_features=shp_lotes,
        out_feature_class=quadras_fc,
        dissolve_field=[campo_bairro, campo_quadra],
        multi_part="MULTI_PART",
        unsplit_lines="DISSOLVE_LINES",
    )

    resumo = {}
    with arcpy.da.SearchCursor(shp_lotes, [campo_bairro, campo_quadra]) as cursor:
        for bairro, quadra in cursor:
            bairro = str(bairro or "").strip().title() or "Sem bairro"
            quadra = str(quadra or "").strip() or "Sem quadra"
            chave = (bairro, quadra)
            if chave not in resumo:
                resumo[chave] = {"bairro": bairro, "quadra": quadra, "area": 0.0, "lotes": 0}
            resumo[chave]["lotes"] += 1

    sr_utm = arcpy.SpatialReference(31983)
    campo_bairro_area = _campo_existente(quadras_fc, [campo_bairro, "bairro"])
    campo_quadra_area = _campo_existente(quadras_fc, [campo_quadra, "quadra"])
    with arcpy.da.SearchCursor(quadras_fc, [campo_bairro_area, campo_quadra_area, "SHAPE@"]) as cursor:
        for bairro, quadra, geom in cursor:
            bairro = str(bairro or "").strip().title() or "Sem bairro"
            quadra = str(quadra or "").strip() or "Sem quadra"
            chave = (bairro, quadra)
            if chave not in resumo:
                resumo[chave] = {"bairro": bairro, "quadra": quadra, "area": 0.0, "lotes": 0}
            if geom:
                try:
                    geom = geom.projectAs(sr_utm)
                except Exception:
                    pass
                resumo[chave]["area"] += float(getattr(geom, "area", 0) or 0)

    return (
        sorted(resumo.values(), key=lambda item: (item["bairro"].lower(), _valor_quadra_para_ordem(item["quadra"]))),
        quadras_fc,
    )


def _criar_tabela_resumo_quadras_municipio(pasta, resumo):
    gdb = _criar_gdb_temporaria(pasta, "dados_prancha_municipal.gdb")
    tabela = str(gdb / "resumo_quadras_municipio")
    if arcpy.Exists(tabela):
        arcpy.management.Delete(tabela)
    arcpy.management.CreateTable(str(gdb), "resumo_quadras_municipio")
    arcpy.management.AddField(tabela, "Bairro", "TEXT", field_length=80, field_alias="Bairro")
    arcpy.management.AddField(tabela, "Quadra", "TEXT", field_length=30, field_alias="Quadra")
    arcpy.management.AddField(tabela, "Area_m2", "TEXT", field_length=30, field_alias="Area (m2)")
    arcpy.management.AddField(tabela, "Lotes", "LONG", field_alias="Qtd. lotes")

    total_area = 0.0
    total_lotes = 0
    with arcpy.da.InsertCursor(tabela, ["Bairro", "Quadra", "Area_m2", "Lotes"]) as cursor:
        for item in resumo:
            area = float(item["area"] or 0)
            lotes = int(item["lotes"] or 0)
            total_area += area
            total_lotes += lotes
            cursor.insertRow([item["bairro"], str(item["quadra"]), decimal_texto(area, 2), lotes])
        cursor.insertRow(["TOTAL", "", decimal_texto(total_area, 2), total_lotes])
    return tabela


def _area_perimetro_feature(feature_class):
    sr_utm = arcpy.SpatialReference(31983)
    area = 0.0
    perimetro = 0.0
    with arcpy.da.SearchCursor(feature_class, ["SHAPE@"]) as cursor:
        for row in cursor:
            geom = row[0]
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            area += float(getattr(geom, "area", 0) or 0)
            perimetro += float(getattr(geom, "length", 0) or 0)
    return area, perimetro


def _angulo_azimute(dx, dy):
    angulo = math.degrees(math.atan2(dx, dy))
    if angulo < 0:
        angulo += 360
    return angulo


def _azimute_texto(angulo):
    graus = int(angulo)
    minutos_float = (angulo - graus) * 60
    minutos = int(minutos_float)
    segundos = int(round((minutos_float - minutos) * 60))
    if segundos == 60:
        segundos = 0
        minutos += 1
    if minutos == 60:
        minutos = 0
        graus += 1
    return f"{graus:03d}°{minutos:02d}'{segundos:02d}\""


def _logradouro_mais_proximo(ponto, eixos, limite=70):
    melhor_nome = ""
    melhor_distancia = None
    for nome, geom in eixos:
        try:
            distancia = ponto.distanceTo(geom)
        except Exception:
            continue
        if melhor_distancia is None or distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_nome = nome
    if melhor_distancia is not None and melhor_distancia <= limite:
        return melhor_nome or "logradouro existente"
    return "area adjacente"


def _carregar_eixos(eixo_viario):
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        return []
    campo_logradouro = _campo_existente(eixo_viario, ["logradouro", "nome", "rua"])
    if not campo_logradouro:
        return []
    sr_utm = arcpy.SpatialReference(31983)
    eixos = []
    with arcpy.da.SearchCursor(eixo_viario, [campo_logradouro, "SHAPE@"]) as cursor:
        for nome, geom in cursor:
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            eixos.append((str(nome or "").strip() or "logradouro existente", geom))
    return eixos


def _vertices_memorial(perimetro_fc, eixo_viario=None):
    sr_utm = arcpy.SpatialReference(31983)
    eixos = _carregar_eixos(eixo_viario)
    segmentos = []
    indice_ponto = 1

    with arcpy.da.SearchCursor(perimetro_fc, ["SHAPE@"]) as cursor:
        for row in cursor:
            geom = row[0]
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            for parte in geom:
                pontos = [p for p in parte if p]
                if len(pontos) < 2:
                    continue
                if abs(pontos[0].X - pontos[-1].X) < 0.001 and abs(pontos[0].Y - pontos[-1].Y) < 0.001:
                    pontos = pontos[:-1]
                if len(pontos) < 2:
                    continue
                nomes = [f"P-{indice_ponto + i:02d}" for i in range(len(pontos))]
                for i, ponto_de in enumerate(pontos):
                    ponto_para = pontos[(i + 1) % len(pontos)]
                    nome_de = nomes[i]
                    nome_para = nomes[(i + 1) % len(pontos)] if i + 1 < len(pontos) else nomes[0]
                    dx = ponto_para.X - ponto_de.X
                    dy = ponto_para.Y - ponto_de.Y
                    distancia = math.hypot(dx, dy)
                    if distancia < 0.01:
                        continue
                    midpoint = arcpy.PointGeometry(
                        arcpy.Point((ponto_de.X + ponto_para.X) / 2, (ponto_de.Y + ponto_para.Y) / 2),
                        sr_utm,
                    )
                    segmentos.append({
                        "de": nome_de,
                        "para": nome_para,
                        "azimute": _azimute_texto(_angulo_azimute(dx, dy)),
                        "distancia": distancia,
                        "este_de": ponto_de.X,
                        "norte_de": ponto_de.Y,
                        "este_para": ponto_para.X,
                        "norte_para": ponto_para.Y,
                        "confrontante": _logradouro_mais_proximo(midpoint, eixos),
                    })
                indice_ponto += len(pontos)
    return segmentos


def _dados_memorial_json(saida_json, municipio, bairros, area, perimetro, segmentos, responsavel_tecnico):
    dados = {
        "municipio": municipio,
        "bairros": bairros,
        "area_total": area,
        "perimetro_total": perimetro,
        "segmentos": segmentos,
        "responsavel": responsavel_tecnico or {},
        "local_data": f"Sao Luis - MA, {datetime.now().strftime('%d/%m/%Y')}.",
    }
    Path(saida_json).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(saida_json)


def _gerar_memorial_geral_pdf(dados_json, saida_pdf):
    try:
        from gerar_memorial_geral import gerar_memorial_pdf
        return gerar_memorial_pdf(dados_json, saida_pdf)
    except Exception as exc:
        arcpy.AddWarning(f"Memorial geral nao foi gerado pelo Python do ArcGIS: {exc}")

    python_externo = _python_externo()
    if not python_externo:
        arcpy.AddWarning("Python externo com reportlab nao encontrado para gerar o memorial geral.")
        return None
    try:
        resultado = subprocess.run(
            [
                python_externo,
                str(Path(__file__).with_name("gerar_memorial_geral.py")),
                "--dados",
                str(dados_json),
                "--saida",
                str(saida_pdf),
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent),
            env=_ambiente_python_externo(),
        )
        if Path(saida_pdf).exists():
            return str(saida_pdf)
        if resultado.returncode != 0:
            arcpy.AddWarning(f"Python externo retornou erro ao gerar memorial: {resultado.stderr or resultado.stdout}")
    except Exception as exc:
        arcpy.AddWarning(f"Memorial geral nao foi gerado pelo Python externo: {exc}")
    return None


def gerar_planta_geral_quadras_arcgis(
    shp_lotes,
    numero_reurb_coletivo,
    municipio,
    bairro,
    shp_bairro=None,
    shp_quadras=None,
    eixo_viario=None,
    shp_frente_lotes=None,
    raster_situacao=None,
    responsavel_tecnico=None,
    pasta_saida=None,
    gerar_memorial=True,
    opcoes_situacao=None,
):
    if not arcpy.Exists(shp_lotes):
        raise ValueError(f"Shapefile de lotes nao encontrado: {shp_lotes}")
    shp_bairro = resolver_shp_bairro(numero_reurb_coletivo, bairro, shp_bairro)
    raster_situacao = resolver_raster_situacao(bairro, raster_situacao)

    pasta = Path(pasta_saida) if pasta_saida else pasta_resultados(numero_reurb_coletivo, bairro)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_base = f"PRANCHA_03-_PLANTA_GERAL_DE_QUADRAS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}"
    aprx_copia = pasta / f"{nome_base}.aprx"
    final_pdf = pasta / f"{nome_base}_ARCGIS.pdf"

    aprx_origem = arcpy.mp.ArcGISProject(projeto_arcgis)
    aprx_origem.saveACopy(str(aprx_copia))
    del aprx_origem

    aprx = arcpy.mp.ArcGISProject(str(aprx_copia))
    aprx_map = _obter_mapa(aprx, "MAP_FRAME", fallback_index=0)
    layout = aprx.listLayouts()[0]

    _limpar_mapa(aprx_map)
    quadro_extent = _adicionar_camadas_planta_geral(
        aprx_map,
        shp_lotes,
        shp_bairro,
        bairro,
        pasta,
        eixo_viario=eixo_viario,
        shp_frente_lotes=shp_frente_lotes,
        shp_quadras=shp_quadras,
    )
    mapa_situacao, escala = _montar_mapa_situacao_e_extent(
        aprx,
        layout,
        aprx_map,
        shp_lotes,
        shp_bairro,
        quadro_extent,
        shp_bairro or shp_lotes,
        raster_situacao=raster_situacao,
        opcoes_situacao=opcoes_situacao,
    )
    resumo = _resumo_quadras(shp_lotes, quadro_extent)
    area_bairro, perimetro_bairro = _area_perimetro_bairro(shp_bairro)
    _ocultar_tabelas(layout)
    tabela_resumo = _criar_tabela_resumo_quadras(pasta, resumo)
    _configurar_quadro_tabela_quadras(layout, aprx_map, tabela_resumo)
    _atualizar_textos_planta_geral(
        layout,
        numero_reurb_coletivo,
        municipio,
        bairro,
        escala,
        resumo,
        area_bairro=area_bairro,
        perimetro_bairro=perimetro_bairro,
        responsavel_tecnico=responsavel_tecnico,
    )
    map_frame = layout.listElements("MAPFRAME_ELEMENT", "MAP_FRAME")[0]
    _remover_camadas_por_nome(aprx, ["Marcacao da frente", "Marcação da frente"])
    _criar_legenda_planta_geral_bairro(layout, map_frame)

    try:
        aprx.save()
    except Exception:
        pass

    layout.exportToPDF(str(final_pdf))
    arcpy.AddMessage(f"Projeto ArcGIS da planta geral salvo em: {aprx_copia}")
    arcpy.AddMessage(f"Planta geral de quadras salva em: {final_pdf}")

    if gerar_memorial and shp_bairro and arcpy.Exists(shp_bairro):
        area_bairro_memorial, perimetro_bairro_memorial = _area_perimetro_feature(shp_bairro)
        segmentos = _vertices_memorial(shp_bairro, eixo_viario)
        dados_memorial = pasta / f"MEMORIAL_EIXO_BAIRRO_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}.json"
        memorial_pdf = pasta / f"MEMORIAL_EIXO_BAIRRO_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}.pdf"
        _dados_memorial_json(
            dados_memorial,
            municipio,
            [bairro],
            area_bairro_memorial,
            perimetro_bairro_memorial,
            segmentos,
            responsavel_tecnico,
        )
        memorial_gerado = _gerar_memorial_geral_pdf(str(dados_memorial), str(memorial_pdf))
        if memorial_gerado:
            arcpy.AddMessage(f"Memorial do eixo/limite do bairro salvo em: {memorial_gerado}")
    return str(final_pdf)


def _atualizar_textos_planta_geral_municipio(
    layout,
    municipio,
    escala,
    area_total,
    perimetro_total,
    total_quadras,
    total_lotes,
    responsavel_tecnico=None,
):
    responsavel_tecnico = responsavel_tecnico or {}
    substituicoes = {
        "{bairro}": "",
        "{municipio}": municipio,
        "{area}": decimal_texto(area_total, 2),
        "{matricula}": "REURB MUNICIPAL",
        "{folha}": "01",
        "{perimetro}": decimal_texto(perimetro_total, 2),
        "{data}": datetime.now().strftime("%d/%m/%Y"),
        "{fusoutm}": "23S",
        "{responsavel_tecnico}": responsavel_tecnico.get("nome", ""),
        "{funcao}": responsavel_tecnico.get("formacao", ""),
        "{n_crea_cau}": responsavel_tecnico.get("registro", ""),
    }
    for elemento in layout.listElements("TEXT_ELEMENT"):
        try:
            texto = elemento.text
            texto = texto.replace("Matrícula:", "Processo:")
            texto = texto.replace("Matricula:", "Processo:")
            texto = texto.replace("Regularização Fundiária Urbana - REURB", "Regularizacao Fundiaria Urbana - REURB")
            for chave, valor in substituicoes.items():
                if chave in texto or chave == elemento.name:
                    texto = texto.replace(chave, valor)
            if "Planta Perimetro" in texto or "Planta Perímetro" in texto or "PLANTA LOTEAMENTO" in texto or "PLANTA GERAL DE QUADRAS" in texto:
                texto = "Levantamento Planialtimetrico Cadastral"
            elemento.text = texto
        except Exception:
            pass
    arcpy.AddMessage(
        "Resumo municipal: "
        f"{total_quadras} quadras, {total_lotes} lotes, "
        f"area {decimal_texto(area_total, 2)} m2, perimetro {decimal_texto(perimetro_total, 2)} m."
    )


def gerar_planta_geral_municipio_arcgis(
    municipio="Peri Mirim",
    shps_lotes=None,
    shps_bairros=None,
    eixo_viario=None,
    raster_situacao=None,
    responsavel_tecnico=None,
    pasta_saida=None,
    gerar_memorial=True,
    opcoes_situacao=None,
):
    pasta = Path(pasta_saida) if pasta_saida else Path(__file__).parent / "resultados" / "peri_mirim_reurb_geral"
    pasta.mkdir(parents=True, exist_ok=True)
    nome_base = f"PRANCHA_01-_PLANTA_GERAL_REURB_{slug_resultado(municipio).upper()}"
    aprx_copia = pasta / f"{nome_base}.aprx"
    final_pdf = pasta / f"{nome_base}_ARCGIS.pdf"
    memorial_pdf = pasta / f"MEMORIAL_GERAL_REURB_{slug_resultado(municipio).upper()}.pdf"
    dados_memorial = pasta / f"MEMORIAL_GERAL_REURB_{slug_resultado(municipio).upper()}.json"

    lotes_municipio, bairros_municipio, perimetro_municipio, bairros_nomes = _preparar_dados_municipio(
        shps_lotes,
        shps_bairros,
        pasta,
    )
    resumo, quadras_fc = _resumo_quadras_municipio(lotes_municipio, pasta)
    area_total, perimetro_total = _area_perimetro_feature(perimetro_municipio)

    aprx_origem = arcpy.mp.ArcGISProject(projeto_arcgis)
    aprx_origem.saveACopy(str(aprx_copia))
    del aprx_origem

    aprx = arcpy.mp.ArcGISProject(str(aprx_copia))
    aprx_map = _obter_mapa(aprx, "MAP_FRAME", fallback_index=0)
    layout = aprx.listLayouts()[0]

    _limpar_mapa(aprx_map)
    bairros_layer = aprx_map.addDataFromPath(bairros_municipio)
    bairros_layer.name = "Perimetros REURB"
    _aplicar_simbolo_bairro(bairros_layer)
    _desativar_rotulos(bairros_layer)

    lotes_layer = aprx_map.addDataFromPath(lotes_municipio)
    lotes_layer.name = "Lotes REURB"
    _aplicar_simbolo_contorno(lotes_layer, [0, 70, 255, 75], 0.22)
    _desativar_rotulos(lotes_layer)

    quadras_layer = aprx_map.addDataFromPath(quadras_fc)
    quadras_layer.name = "Quadras REURB"
    _aplicar_simbolo_quadra_geral(quadras_layer)
    campo_quadra = _campo_existente(quadras_fc, ["quadra"])
    if campo_quadra:
        _configurar_rotulos_quadras(quadras_layer, campo_quadra)

    _, escala = _montar_mapa_situacao_e_extent(
        aprx,
        layout,
        aprx_map,
        lotes_municipio,
        perimetro_municipio,
        perimetro_municipio,
        perimetro_municipio,
        raster_situacao=raster_situacao,
        opcoes_situacao=opcoes_situacao,
    )

    _ocultar_tabelas(layout)
    _remover_legendas(layout)
    tabela_resumo = _criar_tabela_resumo_quadras_municipio(pasta, resumo)
    _configurar_quadro_tabela_quadras(layout, aprx_map, tabela_resumo)
    _atualizar_textos_planta_geral_municipio(
        layout,
        municipio,
        escala,
        area_total,
        perimetro_total,
        len(resumo),
        sum(item["lotes"] for item in resumo),
        responsavel_tecnico=responsavel_tecnico,
    )

    try:
        aprx.save()
    except Exception:
        pass
    layout.exportToPDF(str(final_pdf))
    arcpy.AddMessage(f"Projeto ArcGIS da planta geral municipal salvo em: {aprx_copia}")
    arcpy.AddMessage(f"Planta geral municipal salva em: {final_pdf}")

    memorial_gerado = None
    if gerar_memorial:
        segmentos = _vertices_memorial(perimetro_municipio, eixo_viario)
        _dados_memorial_json(
            dados_memorial,
            municipio,
            bairros_nomes,
            area_total,
            perimetro_total,
            segmentos,
            responsavel_tecnico,
        )
        memorial_gerado = _gerar_memorial_geral_pdf(str(dados_memorial), str(memorial_pdf))
        if memorial_gerado:
            arcpy.AddMessage(f"Memorial geral salvo em: {memorial_gerado}")

    return {
        "plantaGeralMunicipio": str(final_pdf),
        "memorialGeral": memorial_gerado,
        "dadosMemorial": str(dados_memorial) if Path(dados_memorial).exists() else None,
        "aprx": str(aprx_copia),
    }


def gerar_prancha_loteamento_arcgis(
    shp_lotes,
    numero_reurb_coletivo,
    municipio,
    bairro,
    shp_bairro=None,
    shp_quadras=None,
    simbologia_quadras=None,
    raster_situacao=None,
    responsavel_tecnico=None,
    pasta_saida=None,
    anexar_lista=True,
    opcoes_situacao=None,
):
    if not arcpy.Exists(shp_lotes):
        raise ValueError(f"Shapefile de lotes nao encontrado: {shp_lotes}")
    shp_bairro = resolver_shp_bairro(numero_reurb_coletivo, bairro, shp_bairro)
    raster_situacao = resolver_raster_situacao(bairro, raster_situacao)

    pasta = Path(pasta_saida) if pasta_saida else pasta_resultados(numero_reurb_coletivo, bairro)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_base = f"PRANCHA_02-_PLANTA_DO_LOTEAMENTO_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}"
    aprx_copia = pasta / f"{nome_base}.aprx"
    planta_pdf = pasta / f"{nome_base}_arcgis_planta.pdf"
    final_pdf = pasta / f"{nome_base}_ARCGIS.pdf"

    aprx_origem = arcpy.mp.ArcGISProject(projeto_arcgis)
    aprx_origem.saveACopy(str(aprx_copia))
    del aprx_origem

    aprx = arcpy.mp.ArcGISProject(str(aprx_copia))
    aprx_map = _obter_mapa(aprx, "MAP_FRAME", fallback_index=0)
    layout = aprx.listLayouts()[0]

    _limpar_mapa(aprx_map)
    _adicionar_camada_bairro(aprx_map, shp_bairro, bairro)
    contagens = _adicionar_camadas_lotes(aprx_map, shp_lotes, incluir_rotulos=False)
    _adicionar_camada_quadras_loteamento(
        aprx_map,
        shp_lotes,
        pasta,
        shp_quadras=shp_quadras,
        simbologia_quadras=simbologia_quadras,
    )
    _adicionar_rotulos_lotes(aprx_map, shp_lotes)
    _, escala = _montar_mapa_situacao_e_extent(
        aprx,
        layout,
        aprx_map,
        shp_lotes,
        shp_bairro,
        shp_lotes,
        shp_bairro or shp_lotes,
        raster_situacao=raster_situacao,
        opcoes_situacao=opcoes_situacao,
    )
    total_lotes = sum(contagens.values())
    total_beneficiarios = _contar_beneficiarios(shp_lotes)
    area_bairro, perimetro_bairro = _area_perimetro_bairro(shp_bairro)
    _ocultar_tabelas(layout)
    _atualizar_textos_padrao(
        layout,
        numero_reurb_coletivo,
        municipio,
        bairro,
        total_lotes,
        total_beneficiarios,
        escala,
        area_bairro=area_bairro,
        perimetro_bairro=perimetro_bairro,
        responsavel_tecnico=responsavel_tecnico,
    )
    map_frame = layout.listElements("MAPFRAME_ELEMENT", "MAP_FRAME")[0]
    _criar_legenda_layout(layout, map_frame, contagens, bairro)

    try:
        aprx.save()
    except Exception:
        pass

    layout.exportToPDF(str(planta_pdf))
    arcpy.AddMessage(f"PDF da planta ArcGIS exportado em: {planta_pdf}")

    lista_pdf = None
    if anexar_lista:
        lista_pdf = _gerar_lista_pdf_se_possivel(shp_lotes, numero_reurb_coletivo, municipio, bairro, pasta)

    _anexar_pdfs(str(planta_pdf), lista_pdf, str(final_pdf))
    arcpy.AddMessage(f"Projeto ArcGIS da Prancha 02 salvo em: {aprx_copia}")
    arcpy.AddMessage(f"Prancha 02 ArcGIS salva em: {final_pdf}")
    return str(final_pdf)


def ler_input_json(texto):
    if not texto:
        raise ValueError("inputJson vazio.")
    texto = str(texto).strip()
    if texto.startswith("'") and texto.endswith("'"):
        texto = texto[1:-1]
    return _normalizar_input_json(json.loads(texto))


def executar_por_json(input_json):
    input_json = _normalizar_input_json(input_json)
    input_json = _preparar_input_com_camadas_arcgis(input_json)
    dados = input_json.get("dados", {})
    shp_lotes = input_json.get("shpLotes") or dados.get("shpLotes") or dados.get("lotes")
    shp_bairro = input_json.get("shpBairro") or dados.get("shpBairro") or dados.get("bairroCamada")
    shp_quadras = input_json.get("shpQuadras") or dados.get("shpQuadras") or dados.get("quadras")
    simbologia_quadras = (
        input_json.get("simbologiaQuadras")
        or dados.get("simbologiaQuadras")
        or (input_json.get("camadasExportadasArcGIS") or {}).get("simbologiaQuadras")
    )
    shp_frente_lotes = input_json.get("shpFrenteLotes") or input_json.get("pontosFrenteLotes") or dados.get("shpFrenteLotes")
    shps_lotes = input_json.get("shpLotesLista") or input_json.get("shpsLotes") or dados.get("shpLotesLista")
    shps_bairros = input_json.get("shpBairrosLista") or input_json.get("shpsBairros") or dados.get("shpBairrosLista")
    eixo_viario = input_json.get("eixoViario") or dados.get("eixoViario") or r"C:\REURB\SHP\eixo_viario_Peri Mirim.shp"
    raster_situacao = input_json.get("rasterSituacao") or dados.get("rasterSituacao")
    responsavel_tecnico = resolver_responsavel(input_json)
    numero = dados.get("numeroProcessoColetivo") or input_json.get("numeroProcessoColetivo")
    municipio = dados.get("municipio") or input_json.get("municipio") or "Peri Mirim"
    bairro = dados.get("bairro") or input_json.get("bairro") or ""
    pasta_saida = input_json.get("pastaSaida") or dados.get("pastaSaida")
    anexar_lista = bool(
        input_json.get("anexarLista", dados.get("anexarLista", True))
    )
    tipo_prancha = str(input_json.get("tipoPrancha") or dados.get("tipoPrancha") or "").strip().lower()
    opcoes_situacao = _opcoes_planta_situacao(input_json)
    if tipo_prancha in ("plantageralmunicipio", "planta_geral_municipio", "reurb_municipal", "municipio", "geral_municipio"):
        return gerar_planta_geral_municipio_arcgis(
            municipio=municipio,
            shps_lotes=shps_lotes,
            shps_bairros=shps_bairros,
            eixo_viario=eixo_viario,
            raster_situacao=raster_situacao,
            responsavel_tecnico=responsavel_tecnico,
            pasta_saida=pasta_saida,
            gerar_memorial=bool(input_json.get("gerarMemorial", True)),
            opcoes_situacao=opcoes_situacao,
        )
    if not shp_lotes:
        raise ValueError("Informe shpLotes no inputJson.")
    if not numero:
        raise ValueError("Informe dados.numeroProcessoColetivo no inputJson.")
    if not bairro:
        raise ValueError("Informe dados.bairro no inputJson.")
    if tipo_prancha in ("plantageralquadras", "planta_geral_quadras", "geral_quadras", "quadras"):
        return gerar_planta_geral_quadras_arcgis(
            shp_lotes=shp_lotes,
            numero_reurb_coletivo=numero.replace("_", "/"),
            municipio=municipio,
            bairro=bairro,
            shp_bairro=shp_bairro,
            shp_quadras=shp_quadras,
            eixo_viario=eixo_viario,
            shp_frente_lotes=shp_frente_lotes,
            raster_situacao=raster_situacao,
            responsavel_tecnico=responsavel_tecnico,
            pasta_saida=pasta_saida,
            gerar_memorial=bool(input_json.get("gerarMemorial", True)),
            opcoes_situacao=opcoes_situacao,
        )
    return gerar_prancha_loteamento_arcgis(
        shp_lotes=shp_lotes,
        numero_reurb_coletivo=numero.replace("_", "/"),
        municipio=municipio,
        bairro=bairro,
        shp_bairro=shp_bairro,
        shp_quadras=shp_quadras,
        simbologia_quadras=simbologia_quadras,
        raster_situacao=raster_situacao,
        responsavel_tecnico=responsavel_tecnico,
        pasta_saida=pasta_saida,
        anexar_lista=anexar_lista,
        opcoes_situacao=opcoes_situacao,
    )
