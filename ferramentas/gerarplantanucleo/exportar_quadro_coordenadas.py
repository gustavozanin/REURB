# -*- coding: utf-8 -*-

import csv
import json
import os
import subprocess
import tempfile
from pathlib import Path

import arcpy

from normalizacao import decimal_texto


def _linhas_quadro(dados_perimetro):
    linhas = []
    for item in dados_perimetro:
        linhas.append({
            'De': item.get('vertice', ''),
            'Confrontante': item.get('confrontante', '') or '',
            'Azimute': item.get('azimute', ''),
            'Distancia (m)': decimal_texto(item.get('distancia', '')),
            'E': decimal_texto(item.get('eLong', '')),
            'N': decimal_texto(item.get('nLat', '')),
        })
    return linhas


def _texto_responsavel(responsavel_tecnico='', funcao='', n_crea_cau=''):
    nome = responsavel_tecnico or 'Responsavel tecnico'
    detalhes = ' - '.join([valor for valor in [funcao, n_crea_cau] if valor])
    return nome, detalhes


def _titulo_quadro(numero_reurb_coletivo, bairro='', municipio='', objetivo='Regularização Fundiária Urbana - REURB'):
    partes = [
        "Quadro de Coordenadas da Planta Simplificada",
        f"Processo REURB Coletivo: {numero_reurb_coletivo}",
    ]
    if bairro:
        partes.append(f"Bairro: {bairro}")
    if municipio:
        partes.append(f"Município: {municipio}")
    if objetivo:
        partes.append(f"Objetivo: {objetivo}")
    return " | ".join(partes)


def _nota_quadro():
    return (
        "ATENÇÃO: Este anexo corresponde aos vértices simplificados exibidos na planta principal. "
        "A sequência analítica completa do perímetro encontra-se no Memorial Descritivo."
    )


def exportar_quadro_csv(dados_perimetro, numero_reurb_coletivo, pasta_resultados):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    caminho = os.path.join(pasta_resultados, f'quadro_coordenadas_{nome_base}.csv')
    linhas = _linhas_quadro(dados_perimetro)
    campos = ['De', 'Confrontante', 'Azimute', 'Distancia (m)', 'E', 'N']

    with open(caminho, 'w', newline='', encoding='utf-8-sig') as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos, delimiter=';')
        writer.writeheader()
        writer.writerows(linhas)

    arcpy.AddMessage(f"Quadro de coordenadas CSV salvo em: {caminho}")
    return caminho


def exportar_quadro_html(
    dados_perimetro,
    numero_reurb_coletivo,
    pasta_resultados,
    responsavel_tecnico='',
    funcao='',
    n_crea_cau='',
    bairro='',
    municipio='',
    objetivo='Regularização Fundiária Urbana - REURB'
):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    caminho = os.path.join(pasta_resultados, f'quadro_coordenadas_{nome_base}.html')
    linhas = _linhas_quadro(dados_perimetro)
    nome_resp, detalhe_resp = _texto_responsavel(responsavel_tecnico, funcao, n_crea_cau)
    titulo = _titulo_quadro(numero_reurb_coletivo, bairro, municipio, objetivo)
    nota = _nota_quadro()

    linhas_html = "\n".join(
        "<tr>"
        f"<td>{linha['De']}</td>"
        f"<td>{linha['Confrontante']}</td>"
        f"<td>{linha['Azimute']}</td>"
        f"<td>{linha['Distancia (m)']}</td>"
        f"<td>{linha['E']}</td>"
        f"<td>{linha['N']}</td>"
        "</tr>"
        for linha in linhas
    )

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>{titulo}</title>
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    body {{ font-family: Arial, sans-serif; font-size: 7.5px; }}
    h1 {{ font-size: 10px; margin: 0 0 5px 0; font-weight: 600; }}
    .nota-rodape {{ margin-top: 8px; font-size: 7px; color: #333; text-align: left; }}
    table {{ width: 100%; border-collapse: collapse; break-inside: avoid; }}
    th, td {{ border: 1px solid #777; padding: 2px 3px; text-align: center; }}
    th {{ background: #e6e6e6; }}
    .assinatura {{ margin-top: 14px; text-align: center; font-size: 9px; }}
    .linha {{ margin: 16px auto 4px auto; width: 280px; border-top: 1px solid #000; }}
  </style>
</head>
<body>
  <h1>{titulo}</h1>
  <table>
    <thead>
      <tr>
        <th>De</th>
        <th>Confrontante</th>
        <th>Azimute</th>
        <th>Distancia (m)</th>
        <th>E</th>
        <th>N</th>
      </tr>
    </thead>
    <tbody>
      {linhas_html}
    </tbody>
  </table>
  <div class="assinatura">
    <div class="linha"></div>
    <div>{nome_resp}</div>
    <div>{detalhe_resp}</div>
  </div>
  <div class="nota-rodape">{nota}</div>
</body>
</html>
"""

    with open(caminho, 'w', encoding='utf-8') as arquivo:
        arquivo.write(html)

    arcpy.AddMessage(f"Quadro de coordenadas HTML salvo em: {caminho}")
    return caminho


def exportar_quadro_pdf(
    dados_perimetro,
    numero_reurb_coletivo,
    pasta_resultados,
    responsavel_tecnico='',
    funcao='',
    n_crea_cau='',
    bairro='',
    municipio='',
    objetivo='Regularização Fundiária Urbana - REURB'
):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    caminho = os.path.join(pasta_resultados, f'quadro_coordenadas_{nome_base}.pdf')

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except Exception as e:
        arcpy.AddWarning(f"Reportlab indisponivel ({str(e)}). Tentando gerar PDF do quadro via Python externo.")
        pdf_externo = exportar_quadro_pdf_por_python_externo(
            dados_perimetro=dados_perimetro,
            numero_reurb_coletivo=numero_reurb_coletivo,
            pasta_resultados=pasta_resultados,
            responsavel_tecnico=responsavel_tecnico,
            funcao=funcao,
            n_crea_cau=n_crea_cau,
            bairro=bairro,
            municipio=municipio,
            objetivo=objetivo
        )
        if pdf_externo:
            return pdf_externo

        arcpy.AddWarning("PDF do quadro completo nao gerado. O fallback por navegador foi desativado para evitar paginas extras.")
        return None

    linhas = _linhas_quadro(dados_perimetro)
    nome_resp, detalhe_resp = _texto_responsavel(responsavel_tecnico, funcao, n_crea_cau)
    titulo = _titulo_quadro(numero_reurb_coletivo, bairro, municipio, objetivo)

    doc = SimpleDocTemplate(
        caminho,
        pagesize=landscape(A4),
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )
    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'TituloQuadro',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.8,
        leading=10.5,
        spaceAfter=4,
    )
    nota_style = ParagraphStyle(
        'NotaRodape',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#333333'),
    )
    story = [
        Paragraph(titulo, titulo_style),
        Spacer(1, 0.08 * cm)
    ]

    linhas = [
        [
            linha['De'],
            linha['Confrontante'] or '',
            linha['Azimute'],
            linha['Distancia (m)'],
            linha['E'],
            linha['N']
        ]
        for linha in linhas
    ]
    cabecalho = ['De', 'Conf.', 'Azimute', 'D(m)', 'E', 'N']
    larguras_colunas = [1.0 * cm, 3.7 * cm, 2.4 * cm, 1.6 * cm, 2.3 * cm, 2.3 * cm]
    blocos = [linhas[i:i + 30] for i in range(0, len(linhas), 30)]
    estilo = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 5.0),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    for indice in range(0, len(blocos), 2):
        tabelas = []
        for bloco in blocos[indice:indice + 2]:
            tabela = Table([cabecalho] + bloco, repeatRows=1, colWidths=larguras_colunas)
            tabela.setStyle(estilo)
            tabelas.append(tabela)
        while len(tabelas) < 2:
            tabelas.append("")
        pagina = Table([tabelas], colWidths=[13.75 * cm, 13.75 * cm])
        pagina.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(pagina)
        story.append(Spacer(1, 0.18 * cm))

    assinatura = Table([
        [''],
        ['____________________________________________'],
        [nome_resp],
        [detalhe_resp],
    ], colWidths=[10 * cm])
    assinatura.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
        ('TOPPADDING', (0, 0), (0, 0), 10),
    ]))
    story.append(assinatura)
    story.append(Spacer(1, 0.08 * cm))
    story.append(Paragraph(_nota_quadro(), nota_style))
    doc.build(story)

    arcpy.AddMessage(f"Quadro de coordenadas PDF salvo em: {caminho}")
    return caminho


def _edge_executavel():
    candidatos = [
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files (x86)\Microsoft\EdgeCore\msedge.exe',
    ]
    for candidato in candidatos:
        if os.path.exists(candidato):
            return candidato
    return None


def _python_externo_reportlab():
    candidatos = [
        Path.home().joinpath(
            '.cache',
            'codex-runtimes',
            'codex-primary-runtime',
            'dependencies',
            'python',
            'python.exe'
        ),
        Path(r'C:\Users\gusta\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    ]
    for candidato in candidatos:
        if candidato.exists():
            return str(candidato)
    return None


def exportar_quadro_pdf_por_python_externo(
    dados_perimetro,
    numero_reurb_coletivo,
    pasta_resultados,
    responsavel_tecnico='',
    funcao='',
    n_crea_cau='',
    bairro='',
    municipio='',
    objetivo='Regularização Fundiária Urbana - REURB'
):
    python_exe = _python_externo_reportlab()
    if not python_exe:
        arcpy.AddWarning("Python externo com reportlab nao encontrado.")
        return None

    script = Path(__file__).with_name('gerar_pdf_quadro_completo.py')
    if not script.exists():
        arcpy.AddWarning(f"Script do quadro completo nao encontrado: {script}")
        return None

    nome_base = numero_reurb_coletivo.replace('/', '_')
    payload_path = Path(pasta_resultados).joinpath(f'payload_quadro_{nome_base}.json')
    pdf_path = Path(pasta_resultados).joinpath(f'quadro_coordenadas_{nome_base}.pdf')
    payload = {
        'identificacaoPlanilha': {
            'numeroProcessoColetivo': numero_reurb_coletivo,
            'bairro': bairro,
            'objetivo': objetivo,
            'responsavelTecnico': {
                'nome': responsavel_tecnico,
                'formacao': funcao,
                'codigoCredenciamento': n_crea_cau,
            },
            'perimetros': [
                {
                    'dadosPerimetro': dados_perimetro,
                    'municipio': municipio
                }
            ]
        }
    }

    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    try:
        env = os.environ.copy()
        for chave in [
            'PYTHONHOME',
            'PYTHONPATH',
            'PYTHONUSERBASE',
            'CONDA_PREFIX',
            'CONDA_DEFAULT_ENV',
        ]:
            env.pop(chave, None)
        env['PYTHONNOUSERSITE'] = '1'

        resultado = subprocess.run(
            [python_exe, str(script), str(payload_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            env=env
        )
        if resultado.returncode == 0 and pdf_path.exists():
            arcpy.AddMessage(f"Quadro de coordenadas PDF salvo via Python externo: {pdf_path}")
            return str(pdf_path)

        arcpy.AddWarning(
            "PDF do quadro completo nao gerado via Python externo. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"PDF do quadro completo nao gerado via Python externo: {str(e)}")

    return None


def exportar_quadro_pdf_por_html(html_path, pdf_path):
    if not html_path or not os.path.exists(html_path):
        arcpy.AddWarning(f"HTML do quadro nao encontrado para gerar PDF: {html_path}")
        return None

    edge = _edge_executavel()
    if not edge:
        arcpy.AddWarning("PDF do quadro completo nao gerado: Microsoft Edge nao encontrado.")
        return None

    user_data_dir = tempfile.mkdtemp(prefix='edge_reurb_')
    comando = [
        edge,
        '--headless',
        '--disable-gpu',
        '--no-first-run',
        f'--user-data-dir={user_data_dir}',
        f'--print-to-pdf={pdf_path}',
        Path(html_path).resolve().as_uri()
    ]

    try:
        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60
        )
        if resultado.returncode == 0 and os.path.exists(pdf_path):
            arcpy.AddMessage(f"Quadro de coordenadas PDF salvo via navegador: {pdf_path}")
            return pdf_path

        arcpy.AddWarning(
            "PDF do quadro completo nao gerado via navegador. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"PDF do quadro completo nao gerado via navegador: {str(e)}")

    return None


def exportar_quadro_coordenadas(
    dados_perimetro,
    numero_reurb_coletivo,
    pasta_resultados,
    responsavel_tecnico='',
    funcao='',
    n_crea_cau='',
    bairro='',
    municipio='',
    objetivo='Regularização Fundiária Urbana - REURB'
):
    csv_path = exportar_quadro_csv(dados_perimetro, numero_reurb_coletivo, pasta_resultados)
    html_path = exportar_quadro_html(
        dados_perimetro,
        numero_reurb_coletivo,
        pasta_resultados,
        responsavel_tecnico,
        funcao,
        n_crea_cau,
        bairro,
        municipio,
        objetivo
    )
    pdf_path = exportar_quadro_pdf(
        dados_perimetro,
        numero_reurb_coletivo,
        pasta_resultados,
        responsavel_tecnico,
        funcao,
        n_crea_cau,
        bairro,
        municipio,
        objetivo
    )
    return csv_path, html_path, pdf_path
