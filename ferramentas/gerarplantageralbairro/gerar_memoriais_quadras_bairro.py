# -*- coding: utf-8 -*-

import argparse
import html
import json
import math
import os
import subprocess
import sys
import unicodedata
import datetime as dt
from pathlib import Path


PASTA_FERRAMENTA = Path(__file__).parent
PASTA_MOTOR = Path(r"C:\REURB\ferramentas\gerarpranchaloteamento")


def preparar_imports():
    for pasta in [str(PASTA_MOTOR), str(PASTA_FERRAMENTA)]:
        if pasta not in sys.path:
            sys.path.insert(0, pasta)


def slug_resultado(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    import re

    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "valor"


def decimal_texto(valor, casas=2):
    return f"{float(valor or 0):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _campo_existente(arcpy, dataset, candidatos):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(dataset)}
    for candidato in candidatos:
        if candidato.lower() in campos:
            return campos[candidato.lower()]
    return None


def _angulo_azimute(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def _azimute_texto(angulo):
    total = int(round(float(angulo) * 3600))
    graus = (total // 3600) % 360
    minutos = (total % 3600) // 60
    segundos = total % 60
    if graus == 360:
        graus = 0
    return f"{graus:03d}°{minutos:02d}'{segundos:02d}\""


def _carregar_eixos(arcpy, eixo_viario):
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        return []
    campo_nome = _campo_existente(arcpy, eixo_viario, ["logradouro", "nome", "rua"])
    if not campo_nome:
        return []
    sr_utm = arcpy.SpatialReference(31983)
    eixos = []
    with arcpy.da.SearchCursor(eixo_viario, [campo_nome, "SHAPE@"]) as cursor:
        for nome, geom in cursor:
            if not geom:
                continue
            try:
                geom = geom.projectAs(sr_utm)
            except Exception:
                pass
            eixos.append((str(nome or "").strip() or "logradouro existente", geom))
    return eixos


def _logradouro_mais_proximo(arcpy, ponto, eixos, limite=70):
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


def _segmentos_geom(arcpy, geom, prefixo="P", eixos=None):
    sr_utm = arcpy.SpatialReference(31983)
    try:
        geom = geom.projectAs(sr_utm)
    except Exception:
        pass

    segmentos = []
    indice_ponto = 1
    for parte in geom:
        pontos = [p for p in parte if p]
        if len(pontos) < 2:
            continue
        if abs(pontos[0].X - pontos[-1].X) < 0.001 and abs(pontos[0].Y - pontos[-1].Y) < 0.001:
            pontos = pontos[:-1]
        if len(pontos) < 2:
            continue
        nomes = [f"{prefixo}-{indice_ponto + i:02d}" for i in range(len(pontos))]
        for i, ponto_de in enumerate(pontos):
            ponto_para = pontos[(i + 1) % len(pontos)]
            dx = ponto_para.X - ponto_de.X
            dy = ponto_para.Y - ponto_de.Y
            distancia = math.hypot(dx, dy)
            if distancia < 0.01:
                continue
            midpoint = arcpy.PointGeometry(
                arcpy.Point((ponto_de.X + ponto_para.X) / 2, (ponto_de.Y + ponto_para.Y) / 2),
                sr_utm,
            )
            nome_para = nomes[(i + 1) % len(pontos)]
            segmentos.append(
                {
                    "de": nomes[i],
                    "para": nome_para,
                    "azimute": _azimute_texto(_angulo_azimute(dx, dy)),
                    "distancia": distancia,
                    "este_de": ponto_de.X,
                    "norte_de": ponto_de.Y,
                    "este_para": ponto_para.X,
                    "norte_para": ponto_para.Y,
                    "confrontante": _logradouro_mais_proximo(arcpy, midpoint, eixos or []),
                }
            )
        indice_ponto += len(pontos)
    return segmentos


def _dados_quadras(arcpy, shp_quadras, eixo_viario, municipio, bairro, numero, responsavel):
    campo_quadra = _campo_existente(arcpy, shp_quadras, ["quadra"])
    if not campo_quadra:
        raise ValueError(f"Campo quadra nao encontrado em {shp_quadras}")

    sr_utm = arcpy.SpatialReference(31983)
    eixos = _carregar_eixos(arcpy, eixo_viario)
    dados = []
    with arcpy.da.SearchCursor(shp_quadras, [campo_quadra, "SHAPE@"]) as cursor:
        for quadra, geom in cursor:
            if not geom:
                continue
            try:
                geom_utm = geom.projectAs(sr_utm)
            except Exception:
                geom_utm = geom
            quadra_texto = str(quadra or "").strip() or "Sem quadra"
            dados.append(
                {
                    "municipio": municipio,
                    "bairro": bairro,
                    "numero_processo": numero,
                    "quadra": quadra_texto,
                    "area": float(getattr(geom_utm, "area", 0) or 0),
                    "perimetro": float(getattr(geom_utm, "length", 0) or 0),
                    "segmentos": _segmentos_geom(arcpy, geom, prefixo=f"Q{quadra_texto}-P", eixos=eixos),
                    "responsavel": responsavel or {},
                    "local_data": f"Sao Luis - MA, {dt.datetime.now().strftime('%d/%m/%Y')}.",
                }
            )
    return sorted(dados, key=lambda item: _ordem_quadra(item["quadra"]))


def _ordem_quadra(valor):
    texto = str(valor or "").strip()
    if texto.isdigit():
        return (0, int(texto), "")
    return (1, texto.lower(), texto)


def _descricao_segmentos(segmentos):
    if not segmentos:
        return ""
    partes = []
    primeiro = segmentos[0]
    partes.append(
        "Inicia-se a descricao deste perimetro no vertice "
        f"{primeiro['de']}, de coordenadas E= {decimal_texto(primeiro['este_de'], 4)} "
        f"e N= {decimal_texto(primeiro['norte_de'], 4)}, "
    )
    for idx, segmento in enumerate(segmentos):
        prefixo = "" if idx == 0 else "deste segue "
        partes.append(
            f"{prefixo}com azimute de {segmento['azimute']} e distancia de "
            f"{decimal_texto(segmento['distancia'], 2)}m ate o vertice {segmento['para']}, "
            f"de coordenadas E= {decimal_texto(segmento['este_para'], 4)} "
            f"e N= {decimal_texto(segmento['norte_para'], 4)}, confrontando com "
            f"{segmento.get('confrontante') or 'area adjacente'}, "
        )
    partes[-1] = partes[-1].rstrip(", ") + "."
    return "".join(partes)


def _logo_existente():
    candidatos = [
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_Maranhão_(2023-2027).png"),
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃ£o_(2023-2027).png"),
        Path(r"C:\Users\gusta\Downloads\Logo_do_governo_do_MaranhÃƒÂ£o_(2023-2027).png"),
    ]
    for caminho in candidatos:
        if caminho.exists():
            return str(caminho)
    return None


def gerar_pdf_memorial(dados, saida_pdf):
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    saida_pdf = Path(saida_pdf)
    saida_pdf.parent.mkdir(parents=True, exist_ok=True)
    styles = {
        "cabecalho": ParagraphStyle("cabecalho", fontName="Helvetica", fontSize=10, leading=12, alignment=TA_CENTER),
        "titulo": ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=12, leading=15, alignment=TA_CENTER),
        "normal": ParagraphStyle("normal", fontName="Helvetica", fontSize=10.5, leading=13.2, alignment=TA_LEFT),
        "justificado": ParagraphStyle("justificado", fontName="Helvetica", fontSize=10.5, leading=13.2, alignment=TA_JUSTIFY),
        "assinatura": ParagraphStyle("assinatura", fontName="Helvetica", fontSize=10, leading=12, alignment=TA_CENTER),
    }

    story = []
    logo = _logo_existente()
    if logo:
        story.append(Image(logo, width=5.0 * cm, height=1.0 * cm, kind="proportional"))
    story.extend(
        [
            Paragraph("ESTADO DO MARANHAO", styles["cabecalho"]),
            Paragraph("SECRETARIA DE ESTADO DA AGRICULTURA FAMILIAR - SAF", styles["cabecalho"]),
            Paragraph("INSTITUTO DE COLONIZACAO E TERRAS DO MARANHAO - ITERMA", styles["cabecalho"]),
            Spacer(1, 0.6 * cm),
            Paragraph("MEMORIAL DESCRITIVO DA QUADRA", styles["titulo"]),
            Spacer(1, 0.45 * cm),
            Paragraph(f"Municipio/UF: {html.escape(dados['municipio'])} - MA", styles["normal"]),
            Paragraph(f"Bairro/Nucleo: {html.escape(dados['bairro'])}", styles["normal"]),
            Paragraph(f"Processo: {html.escape(dados.get('numero_processo', ''))}", styles["normal"]),
            Paragraph(f"Quadra: {html.escape(str(dados['quadra']))}", styles["normal"]),
            Spacer(1, 0.25 * cm),
            Paragraph(f"Area: {decimal_texto(dados['area'], 2)} m2", styles["normal"]),
            Paragraph(f"Perimetro: {decimal_texto(dados['perimetro'], 2)} m", styles["normal"]),
            Spacer(1, 0.65 * cm),
            Paragraph("_" * 100, styles["cabecalho"]),
            Paragraph("DESCRICAO DO PERIMETRO DA QUADRA", styles["titulo"]),
            Paragraph("_" * 100, styles["cabecalho"]),
            Spacer(1, 0.25 * cm),
            Paragraph(html.escape(_descricao_segmentos(dados.get("segmentos", []))), styles["justificado"]),
            Spacer(1, 0.35 * cm),
            Paragraph(
                "Todas as coordenadas aqui descritas estao georreferenciadas ao Sistema Geodesico Brasileiro (SGB) "
                "e encontram-se representadas no Sistema UTM, referenciadas ao SIRGAS 2000, Fuso 23S. "
                "A area, o perimetro, os azimutes e as distancias foram calculados no plano de projecao UTM.",
                styles["justificado"],
            ),
            Spacer(1, 0.65 * cm),
            Paragraph(html.escape(dados.get("local_data", "")), styles["cabecalho"]),
            Spacer(1, 1.0 * cm),
            Paragraph("________________________________________", styles["assinatura"]),
            Paragraph("Responsavel Tecnico", styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("nome", "")), styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("formacao", "")), styles["assinatura"]),
            Paragraph(html.escape(dados.get("responsavel", {}).get("registro", "")), styles["assinatura"]),
        ]
    )

    doc = SimpleDocTemplate(
        str(saida_pdf),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.6 * cm,
    )
    doc.build(story)
    return str(saida_pdf)


def _python_externo():
    candidatos = [
        Path(r"C:\Users\gusta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    ]
    if os.environ.get("CODEX_PYTHON"):
        candidatos.append(Path(os.environ["CODEX_PYTHON"]))
    for caminho in candidatos:
        if caminho.exists() and caminho.is_file():
            return str(caminho)
    return None


def _renderizar_pdf(dados_json, saida_pdf):
    dados = json.loads(Path(dados_json).read_text(encoding="utf-8"))
    try:
        return gerar_pdf_memorial(dados, saida_pdf)
    except Exception:
        python_externo = _python_externo()
        if not python_externo:
            raise
        env = os.environ.copy()
        for chave in ["PYTHONHOME", "PYTHONPATH", "CONDA_PREFIX", "CONDA_DEFAULT_ENV", "CONDA_PYTHON_EXE"]:
            env.pop(chave, None)
        env["PYTHONNOUSERSITE"] = "1"
        resultado = subprocess.run(
            [
                python_externo,
                str(Path(__file__)),
                "--render-json",
                str(dados_json),
                "--saida",
                str(saida_pdf),
            ],
            cwd=str(PASTA_FERRAMENTA),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if not Path(saida_pdf).exists():
            raise RuntimeError(resultado.stderr or resultado.stdout or "Falha ao renderizar PDF.")
        return str(saida_pdf)


def _mesclar_pdfs(pdfs, saida_pdf):
    if not pdfs:
        return None
    try:
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        for pdf in pdfs:
            reader = PdfReader(str(pdf))
            for page in reader.pages:
                writer.add_page(page)
        with open(saida_pdf, "wb") as arquivo:
            writer.write(arquivo)
        return str(saida_pdf)
    except Exception:
        return None


def _camada_aprx_por_nome(arcpy, aprx, nomes):
    nomes_normalizados = {str(nome).strip().lower() for nome in nomes if nome}
    for mapa in aprx.listMaps():
        for layer in mapa.listLayers():
            try:
                if layer.isFeatureLayer and str(layer.name).strip().lower() in nomes_normalizados:
                    return layer
            except Exception:
                pass
    raise ValueError(f"Camada nao encontrada no APRX: {', '.join(nomes)}")


def _fonte_camada(layer):
    try:
        props = layer.connectionProperties or {}
        if str(props.get("workspace_factory", "")).lower() == "featureservice":
            url = (props.get("connection_info") or {}).get("url")
            dataset = props.get("dataset")
            if url and dataset not in (None, ""):
                return f"{str(url).rstrip('/')}/{dataset}"
    except Exception:
        pass
    try:
        data_source = layer.dataSource
        if data_source:
            return data_source
    except Exception:
        pass
    return layer


def _preparar_camadas_atualizadas(arcpy, input_json):
    from gerar_prancha_loteamento_arcgis import (
        _contar_features,
        _exportar_eixo_por_bairro,
        _exportar_feature_filtrado,
        _where_por_campos,
    )

    dados = input_json.get("dados", {}) or {}
    numero = dados.get("numeroProcessoColetivo") or input_json.get("numeroProcessoColetivo")
    bairro = dados.get("bairro") or input_json.get("bairro")
    municipio = dados.get("municipio") or input_json.get("municipio") or "municipio"
    if not numero:
        raise ValueError("Informe dados.numeroProcessoColetivo.")
    if not bairro:
        raise ValueError("Informe dados.bairro.")

    aprx_camadas = input_json.get("aprxCamadas") or input_json.get("projetoCamadasArcGIS")
    usar_current = bool(input_json.get("usarProjetoAtualArcGIS")) or str(aprx_camadas or "").strip().upper() == "CURRENT"
    if not aprx_camadas and not usar_current:
        aprx_camadas = r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx"
    if not usar_current and not Path(aprx_camadas).exists():
        raise ValueError(f"APRX das camadas nao encontrado: {aprx_camadas}")

    nomes = input_json.get("camadasArcGIS") or {}
    pasta_saida = input_json.get("pastaSaida") or dados.get("pastaSaida")
    pasta_base = Path(pasta_saida).parent if pasta_saida else PASTA_FERRAMENTA / "resultados"
    pasta = pasta_base / slug_resultado(municipio) / slug_resultado(bairro) / slug_resultado(numero)
    pasta.mkdir(parents=True, exist_ok=True)

    aprx = arcpy.mp.ArcGISProject("CURRENT" if usar_current else str(aprx_camadas))
    try:
        layer_lotes = _fonte_camada(_camada_aprx_por_nome(arcpy, aprx, [nomes.get("lotes", "Lotes")]))
        layer_bairro = _fonte_camada(_camada_aprx_por_nome(arcpy, aprx, [nomes.get("bairro", "Bairro")]))
        layer_quadras = _fonte_camada(_camada_aprx_por_nome(arcpy, aprx, [nomes.get("quadras", "Quadras")]))
        layer_eixo = _fonte_camada(_camada_aprx_por_nome(
            arcpy,
            aprx,
            [nomes.get("eixoViario", "Eixo Viario"), nomes.get("eixo", "Eixo Viario")],
        ))

        layer_lotes_base = f"lyr_mem_quadras_lotes_{slug_resultado(numero)}"
        layer_bairro_base = f"lyr_mem_quadras_bairro_{slug_resultado(numero)}"
        layer_quadras_base = f"lyr_mem_quadras_quadras_{slug_resultado(numero)}"
        layer_eixo_base = f"lyr_mem_quadras_eixo_{slug_resultado(numero)}"
        for nome in [layer_lotes_base, layer_bairro_base, layer_quadras_base, layer_eixo_base]:
            try:
                arcpy.management.Delete(nome)
            except Exception:
                pass
        arcpy.management.MakeFeatureLayer(layer_lotes, layer_lotes_base)
        arcpy.management.MakeFeatureLayer(layer_bairro, layer_bairro_base)
        arcpy.management.MakeFeatureLayer(layer_quadras, layer_quadras_base)
        arcpy.management.MakeFeatureLayer(layer_eixo, layer_eixo_base)

        where_lotes_numero = _where_por_campos(layer_lotes_base, [(["n_coletivo", "coletivo", "reurb"], numero)])
        where_lotes_bairro = _where_por_campos(layer_lotes_base, [(["bairro"], bairro)])
        where_bairro_completo = _where_por_campos(
            layer_bairro_base,
            [(["n_coletivo", "coletivo", "reurb"], numero), (["nome", "bairro"], bairro)],
        )
        where_bairro_numero = _where_por_campos(layer_bairro_base, [(["n_coletivo", "coletivo", "reurb"], numero)])
        where_bairro_nome = _where_por_campos(layer_bairro_base, [(["nome", "bairro"], bairro)])
        shp_bairro = _exportar_feature_filtrado(
            layer_bairro_base,
            pasta / "bairro.shp",
            [where_bairro_completo, where_bairro_numero, where_bairro_nome],
        )
        shp_lotes = _exportar_feature_filtrado(layer_lotes_base, pasta / "lotes.shp", [where_lotes_numero, where_lotes_bairro])
        shp_quadras = _exportar_feature_filtrado(
            layer_quadras_base,
            pasta / "quadras.shp",
            [
                _where_por_campos(layer_quadras_base, [(["n_coletivo", "coletivo", "reurb"], numero)]),
                _where_por_campos(layer_quadras_base, [(["bairro"], bairro)]),
            ],
        )
        eixo_viario = _exportar_eixo_por_bairro(layer_eixo_base, shp_bairro, pasta / "eixo_viario.shp")
    finally:
        for nome in [
            locals().get("layer_lotes_base"),
            locals().get("layer_bairro_base"),
            locals().get("layer_quadras_base"),
            locals().get("layer_eixo_base"),
        ]:
            if nome:
                try:
                    arcpy.management.Delete(nome)
                except Exception:
                    pass
        del aprx

    atualizado = dict(input_json)
    atualizado["shpLotes"] = shp_lotes
    atualizado["shpBairro"] = shp_bairro
    atualizado["shpQuadras"] = shp_quadras
    atualizado["eixoViario"] = eixo_viario
    atualizado["camadasExportadasArcGIS"] = {
        "aprx": str(aprx_camadas),
        "pasta": str(pasta),
        "lotes": shp_lotes,
        "bairro": shp_bairro,
        "quadras": shp_quadras,
        "eixoViario": eixo_viario,
    }
    arcpy.AddMessage(f"Camadas atuais exportadas do ArcGIS Pro em: {pasta}")
    arcpy.AddMessage(f"Lotes exportados: {_contar_features(shp_lotes)}")
    arcpy.AddMessage(f"Bairro exportado: {_contar_features(shp_bairro)}")
    arcpy.AddMessage(f"Quadras exportadas: {_contar_features(shp_quadras)}")
    arcpy.AddMessage(f"Eixos exportados: {_contar_features(eixo_viario)}")
    return atualizado


def gerar_memoriais_por_json(input_json):
    preparar_imports()
    import arcpy
    from responsaveis_tecnicos import resolver_responsavel

    entrada = dict(input_json or {})
    dados = dict(entrada.get("dados") or {})
    entrada["dados"] = dados

    exportar = entrada.get("exportarCamadasArcGIS", True)
    if exportar:
        try:
            atualizado = _preparar_camadas_atualizadas(arcpy, entrada)
        except Exception:
            if not (entrada.get("shpQuadras") or dados.get("shpQuadras") or dados.get("quadras")):
                raise
            atualizado = entrada
    else:
        atualizado = entrada
    dados = atualizado.get("dados", {}) or {}
    municipio = dados.get("municipio") or atualizado.get("municipio") or "Peri Mirim"
    bairro = dados.get("bairro") or atualizado.get("bairro") or ""
    numero = dados.get("numeroProcessoColetivo") or atualizado.get("numeroProcessoColetivo") or ""
    shp_quadras = atualizado.get("shpQuadras") or dados.get("shpQuadras")
    eixo_viario = atualizado.get("eixoViario") or dados.get("eixoViario")
    if not shp_quadras or not arcpy.Exists(shp_quadras):
        raise ValueError("Camada de quadras nao encontrada apos exportar as camadas atuais.")

    pasta_saida = Path(
        atualizado.get("pastaSaidaMemoriais")
        or atualizado.get("pastaMemoriais")
        or PASTA_FERRAMENTA
        / "resultados"
        / "memoriais_quadras"
        / slug_resultado(municipio)
        / slug_resultado(bairro)
        / slug_resultado(numero)
    )
    pasta_json = pasta_saida / "dados_json"
    pasta_pdf = pasta_saida / "pdfs"
    pasta_json.mkdir(parents=True, exist_ok=True)
    pasta_pdf.mkdir(parents=True, exist_ok=True)

    responsavel = resolver_responsavel(atualizado)
    memoriais = _dados_quadras(arcpy, shp_quadras, eixo_viario, municipio, bairro, numero, responsavel)
    pdfs = []
    jsons = []
    for item in memoriais:
        quadra_slug = slug_resultado(item["quadra"])
        nome_base = f"MEMORIAL_QUADRA_{quadra_slug.upper()}_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}"
        json_path = pasta_json / f"{nome_base}.json"
        pdf_path = pasta_pdf / f"{nome_base}.pdf"
        json_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        _renderizar_pdf(json_path, pdf_path)
        jsons.append(str(json_path))
        pdfs.append(str(pdf_path))

    consolidado = pasta_saida / f"MEMORIAIS_QUADRAS_{slug_resultado(municipio).upper()}_{slug_resultado(bairro).upper()}_COMPLETO.pdf"
    consolidado_final = _mesclar_pdfs(pdfs, consolidado)
    saida = {
        "pronto": True,
        "municipio": municipio,
        "bairro": bairro,
        "numeroProcessoColetivo": numero,
        "pastaSaida": str(pasta_saida),
        "pastaPDFs": str(pasta_pdf),
        "quantidadeQuadras": len(pdfs),
        "pdfs": pdfs,
        "jsons": jsons,
        "pdfConsolidado": consolidado_final,
        "camadasExportadasArcGIS": atualizado.get("camadasExportadasArcGIS"),
    }
    return saida


def main():
    parser = argparse.ArgumentParser(description="Gera memoriais descritivos por quadra.")
    parser.add_argument("--input", help="JSON de entrada da ferramenta.")
    parser.add_argument("--saida-json", help="Arquivo JSON de saida.")
    parser.add_argument("--render-json", help="Renderiza um JSON de memorial em PDF.")
    parser.add_argument("--saida", help="PDF de saida para --render-json.")
    args = parser.parse_args()

    if args.render_json:
        if not args.saida:
            raise ValueError("Informe --saida para renderizar o PDF.")
        print(gerar_pdf_memorial(json.loads(Path(args.render_json).read_text(encoding="utf-8")), args.saida))
        return

    if not args.input:
        raise ValueError("Informe --input.")
    entrada = json.loads(Path(args.input).read_text(encoding="utf-8"))
    saida = gerar_memoriais_por_json(entrada)
    if args.saida_json:
        Path(args.saida_json).write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
