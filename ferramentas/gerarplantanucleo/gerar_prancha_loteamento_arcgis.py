# -*- coding: utf-8 -*-

import json
import os
import re
import shutil
import subprocess
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import arcpy

from caminhos_gerais import projeto_arcgis


PROJETO_DADOS_ARCGIS = Path(r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx")


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
    shp_origem = exportar_camada_do_projeto_origem("Bairro", numero_reurb_coletivo, bairro)
    if shp_origem:
        return shp_origem
    if shp_bairro and arcpy.Exists(shp_bairro):
        arcpy.AddWarning("Usando bairro informado como fallback; fonte principal do projeto de origem indisponivel.")
        return shp_bairro
    return None


def resolver_fc_lotes(numero_reurb_coletivo, shp_lotes=None):
    fc_origem = exportar_camada_do_projeto_origem("Lotes", numero_reurb_coletivo)
    if fc_origem:
        return fc_origem
    if shp_lotes and arcpy.Exists(shp_lotes):
        arcpy.AddWarning("Usando lotes informados como fallback; fonte principal do projeto de origem indisponivel.")
        return shp_lotes
    return None


def resolver_fc_quadras(numero_reurb_coletivo, shp_quadras=None):
    fc_origem = exportar_camada_do_projeto_origem("Quadras", numero_reurb_coletivo)
    if fc_origem:
        return fc_origem
    if shp_quadras and arcpy.Exists(shp_quadras):
        arcpy.AddWarning("Usando quadras informadas como fallback; fonte principal do projeto de origem indisponivel.")
        return shp_quadras
    return None


def resolver_fc_eixo_viario(shp_eixo=None):
    fc_origem = exportar_camada_do_projeto_origem("Eixo Viario", None)
    if fc_origem:
        return fc_origem
    if shp_eixo and arcpy.Exists(shp_eixo):
        arcpy.AddWarning("Usando eixo viario informado como fallback; fonte principal do projeto de origem indisponivel.")
        return shp_eixo
    return None


def _camada_do_projeto_origem(nome_camada):
    if not PROJETO_DADOS_ARCGIS.exists():
        return None

    try:
        aprx = arcpy.mp.ArcGISProject(str(PROJETO_DADOS_ARCGIS))
    except Exception as exc:
        arcpy.AddWarning(f"Nao foi possivel abrir projeto de origem dos dados: {exc}")
        return None

    nome_normalizado = nome_camada.lower()
    for mapa in aprx.listMaps():
        for layer in mapa.listLayers():
            if layer.isFeatureLayer and layer.name.lower() == nome_normalizado:
                return layer

    arcpy.AddWarning(f"Camada {nome_camada} nao encontrada no projeto de origem dos dados.")
    return None


def exportar_camada_do_projeto_origem(nome_camada, numero_reurb_coletivo=None, bairro=None):
    camada = _camada_do_projeto_origem(nome_camada)
    if not camada:
        return None

    workspace = Path(__file__).parent / "temp" / "reurb_temp.gdb"
    if not arcpy.Exists(str(workspace)):
        workspace.parent.mkdir(parents=True, exist_ok=True)
        arcpy.management.CreateFileGDB(str(workspace.parent), workspace.name)

    if numero_reurb_coletivo:
        nome_base = f"{slug_resultado(nome_camada)}_{slug_resultado(bairro) if bairro else 'dados'}_{numero_reurb_coletivo.replace('/', '_')}"
    else:
        nome_base = f"{slug_resultado(nome_camada)}_origem"
    saida = workspace / nome_base
    if arcpy.Exists(str(saida)):
        arcpy.Delete_management(str(saida))

    where = None
    if numero_reurb_coletivo:
        campo_processo = _campo_existente(camada, ["n_coletivo", "n_coletiv"])
        if not campo_processo:
            arcpy.AddWarning(f"Campo de processo nao encontrado em {nome_camada}.")
            return None
        where = f"{arcpy.AddFieldDelimiters(camada, campo_processo)} = '{numero_reurb_coletivo}'"

    selecionado = arcpy.Select_analysis(
        in_features=camada,
        out_feature_class=str(saida),
        where_clause=where,
    )

    total = int(arcpy.management.GetCount(selecionado)[0])
    if total == 0:
        arcpy.Delete_management(str(selecionado))
        arcpy.AddWarning(f"Nenhuma feicao em {nome_camada} encontrada no projeto de origem para {numero_reurb_coletivo}.")
        return None

    arcpy.AddMessage(f"{nome_camada} exportado do projeto de origem: {saida}")
    return str(saida)


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


def _adicionar_camada_bairro(aprx_map, shp_bairro):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        arcpy.AddWarning("Camada de bairro nao informada/encontrada. A planta seguira somente com lotes.")
        return None
    layer = aprx_map.addDataFromPath(shp_bairro)
    layer.name = "Perimetro do bairro"
    _aplicar_simbolo_bairro(layer)
    arcpy.AddMessage(f"Camada de bairro adicionada ao fundo: {shp_bairro}")
    return layer


def _area_perimetro_bairro(shp_bairro):
    if not shp_bairro or not arcpy.Exists(shp_bairro):
        return None, None
    sr_utm = arcpy.SpatialReference(31983)
    workspace = arcpy.env.scratchGDB or arcpy.env.scratchFolder
    if not workspace:
        workspace = str(Path(__file__).parent / "temp" / "reurb_temp.gdb")
        if not arcpy.Exists(workspace):
            arcpy.management.CreateFileGDB(str(Path(workspace).parent), Path(workspace).name)

    sufixo = uuid.uuid4().hex[:8]
    bairro_reprojetado = os.path.join(workspace, f"bairro_area_prancha_{sufixo}")
    arcpy.Project_management(shp_bairro, bairro_reprojetado, sr_utm)
    arcpy.AddFields_management(
        bairro_reprojetado,
        [
            ["area_m2", "DOUBLE", "area_m2"],
            ["perimetro_m", "DOUBLE", "perimetro_m"],
        ],
    )
    arcpy.CalculateGeometryAttributes_management(
        in_features=bairro_reprojetado,
        geometry_property=[
            ["area_m2", "AREA"],
            ["perimetro_m", "PERIMETER_LENGTH"],
        ],
        length_unit="METERS",
        area_unit="SQUARE_METERS",
        coordinate_system=sr_utm,
    )

    area = 0.0
    perimetro = 0.0
    with arcpy.da.SearchCursor(bairro_reprojetado, ["area_m2", "perimetro_m"]) as cursor:
        for area_m2, perimetro_m in cursor:
            area += float(area_m2 or 0)
            perimetro += float(perimetro_m or 0)

    arcpy.Delete_management(bairro_reprojetado)
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
        layer.showLabels = True
        for label_class in layer.listLabelClasses():
            label_class.expression = f"'Q' + Text($feature.{campo_quadra}) + '-L' + Text($feature.{campo_lote})"
            try:
                label_class.expressionEngine = "Arcade"
            except Exception:
                pass
            label_class.visible = True

        cim = layer.getDefinition("V3")
        for label_class in getattr(cim, "labelClasses", []):
            label_class.visible = True
            try:
                label_class.expression = f"'Q' + Text($feature.{campo_quadra}) + '-L' + Text($feature.{campo_lote})"
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


def _adicionar_camadas_lotes(aprx_map, shp_lotes):
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

    rotulos = aprx_map.addDataFromPath(shp_lotes)
    rotulos.name = "Rotulos dos lotes"
    _ocultar_simbolo(rotulos)
    _configurar_rotulos_lotes(rotulos, campo_quadra, campo_lote)
    return contagens


def _ajustar_extent(layout, aprx_map, feature_extent):
    frames = layout.listElements("MAPFRAME_ELEMENT", "MAP_FRAME")
    if not frames:
        frames = layout.listElements("MAPFRAME_ELEMENT")
    if not frames:
        raise ValueError("Layout nao possui MAP_FRAME.")

    map_frame = frames[0]
    map_frame.map = aprx_map
    extent = arcpy.Describe(feature_extent).extent
    map_frame.camera.setExtent(extent)
    escala = map_frame.camera.scale * 1.20
    escala = (((escala // 100) + 1) * 100)
    map_frame.camera.scale = escala
    aprx_map.defaultCamera = map_frame.camera

    for frame in layout.listElements("MAPFRAME_ELEMENT", "OVERVIEW_MAP_FRAME"):
        try:
            frame.map = aprx_map
            frame.camera.setExtent(extent)
            frame.camera.scale = escala * 1.35
        except Exception:
            pass

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
):
    hoje = datetime.now().strftime("%d/%m/%Y")
    area_texto = decimal_texto(area_bairro) if area_bairro else ""
    perimetro_texto = decimal_texto(perimetro_bairro) if perimetro_bairro else ""
    substituicoes = {
        "{bairro}": bairro,
        "{municipio}": municipio,
        "{area}": area_texto,
        "{matricula}": numero,
        "{folha}": "02",
        "{perimetro}": perimetro_texto,
        "{data}": hoje,
        "{fusoutm}": "23S",
        "{responsavel_tecnico}": "",
        "{funcao}": "",
        "{n_crea_cau}": "",
    }
    for elemento in layout.listElements("TEXT_ELEMENT"):
        try:
            texto = elemento.text
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
                elemento.text = f"Planta do Loteamento - Bairro {bairro}"
            if "Regularização Fundiária Urbana" in elemento.text or "Regularizacao Fundiaria Urbana" in elemento.text:
                elemento.text = "Planta georreferenciada dos lotes"
        except Exception:
            pass

    _texto_existente(
        layout,
        "titulo_prancha_loteamento",
        f"PLANTA LOTEAMENTO - {municipio.upper()} - {bairro.upper()}",
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
        subprocess.run(
            [
                python_externo,
                str(Path(__file__).with_name("gerar_prancha_loteamento.py")),
                "--shp",
                str(shp_lotes),
                "--numero",
                str(numero),
                "--municipio",
                str(municipio),
                "--bairro",
                str(bairro),
                "--saida",
                str(pasta),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        nome_base = f"PRANCHA_02_LISTA_DE_BENEFICIARIOS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}.pdf"
        lista_pdf = pasta / nome_base
        if lista_pdf.exists():
            arcpy.AddMessage(f"Lista de beneficiarios gerada pelo Python externo: {lista_pdf}")
            return str(lista_pdf)
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
            )
            return saida_pdf
        except Exception as exc:
            arcpy.AddWarning(f"Nao foi possivel anexar lista pelo Python externo: {exc}")

    shutil.copy2(planta_pdf, saida_pdf)
    return saida_pdf


def _python_externo():
    candidatos = [
        Path(r"C:\Users\gusta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        Path(os.environ.get("CODEX_PYTHON", "")),
    ]
    for caminho in candidatos:
        if caminho and caminho.exists():
            return str(caminho)
    return None


def gerar_prancha_loteamento_arcgis(
    shp_lotes=None,
    numero_reurb_coletivo=None,
    municipio=None,
    bairro=None,
    shp_bairro=None,
    pasta_saida=None,
    anexar_lista=True,
):
    if not numero_reurb_coletivo:
        raise ValueError("Informe numero_reurb_coletivo.")
    if not bairro:
        raise ValueError("Informe bairro.")
    municipio = municipio or ""
    shp_lotes = resolver_fc_lotes(numero_reurb_coletivo, shp_lotes)
    if not shp_lotes or not arcpy.Exists(shp_lotes):
        raise ValueError(f"Camada de lotes nao encontrada para {numero_reurb_coletivo}.")
    shp_bairro = resolver_shp_bairro(numero_reurb_coletivo, bairro, shp_bairro)

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
    aprx_map = aprx.listMaps()[0]
    layout = aprx.listLayouts()[0]

    _limpar_mapa(aprx_map)
    _adicionar_camada_bairro(aprx_map, shp_bairro)
    contagens = _adicionar_camadas_lotes(aprx_map, shp_lotes)
    escala = _ajustar_extent(layout, aprx_map, shp_lotes)
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
    )

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
    texto = texto.strip()
    if texto.startswith("'") and texto.endswith("'"):
        texto = texto[1:-1]
    return json.loads(texto)


def executar_por_json(input_json):
    dados = input_json.get("dados", {})
    shp_lotes = input_json.get("shpLotes") or dados.get("shpLotes") or dados.get("lotes")
    shp_bairro = input_json.get("shpBairro") or dados.get("shpBairro") or dados.get("bairroCamada")
    numero = dados.get("numeroProcessoColetivo") or input_json.get("numeroProcessoColetivo")
    municipio = dados.get("municipio") or input_json.get("municipio") or "Peri Mirim"
    bairro = dados.get("bairro") or input_json.get("bairro") or ""
    pasta_saida = input_json.get("pastaSaida") or dados.get("pastaSaida")
    anexar_lista = bool(input_json.get("anexarLista", True))
    if not numero:
        raise ValueError("Informe dados.numeroProcessoColetivo no inputJson.")
    if not bairro:
        raise ValueError("Informe dados.bairro no inputJson.")
    return gerar_prancha_loteamento_arcgis(
        shp_lotes=shp_lotes,
        numero_reurb_coletivo=numero.replace("_", "/"),
        municipio=municipio,
        bairro=bairro,
        shp_bairro=shp_bairro,
        pasta_saida=pasta_saida,
        anexar_lista=anexar_lista,
    )
