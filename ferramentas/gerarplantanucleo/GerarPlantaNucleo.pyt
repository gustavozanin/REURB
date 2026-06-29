# -*- coding: utf-8 -*-

import os
import sys
import importlib
import shutil
import re
import unicodedata
import subprocess
import base64
from pathlib import Path

#Importações externas
import json
import arcpy
from datetime import datetime


def ler_input_json(valor):
    texto = (valor or '').strip()
    exemplo = (
        '{"dados":{"numeroProcessoColetivo":"050601273/2026",'
        '"bairro":"Centro","matricula":""},'
        '"responsavelTecnico":"leandro_miranda_da_silva",'
        '"forcarGeracao":true}'
    )

    if not texto:
        raise ValueError(f"inputJson vazio. Cole um JSON valido. Exemplo: {exemplo}")

    if (texto.startswith("'") and texto.endswith("'")) or (texto.startswith('"') and texto.endswith('"')):
        texto_sem_aspas = texto[1:-1].strip()
        if texto_sem_aspas.startswith('{'):
            texto = texto_sem_aspas

    try:
        dados = json.loads(texto)
        if isinstance(dados, str):
            dados = json.loads(dados)
    except json.JSONDecodeError as erro:
        raise ValueError(
            f"inputJson invalido na linha {erro.lineno}, coluna {erro.colno}. "
            f"Cole o JSON sem texto antes/depois. Exemplo: {exemplo}"
        )

    if not isinstance(dados, dict) or 'dados' not in dados:
        raise ValueError(f"inputJson deve conter a chave 'dados'. Exemplo: {exemplo}")

    return dados


def arquivo_base64(caminho):
    if not caminho or not os.path.exists(caminho):
        return ''
    with open(caminho, 'rb') as arquivo:
        return base64.b64encode(arquivo.read()).decode('utf-8')


def anexar_pdf_anexo(pdf_principal, pdf_anexo, sufixo_saida, descricao):
    if not pdf_anexo or not os.path.exists(pdf_anexo):
        return pdf_principal

    try:
        pdf_completo = os.path.splitext(pdf_principal)[0] + sufixo_saida + '.pdf'
        pdf_doc = arcpy.mp.PDFDocumentCreate(pdf_completo)
        pdf_doc.appendPages(pdf_principal)
        pdf_doc.appendPages(pdf_anexo)
        pdf_doc.saveAndClose()
        arcpy.AddMessage(f"PDF completo com {descricao} salvo em: {pdf_completo}")
        return pdf_completo
    except Exception as e:
        arcpy.AddWarning(f"Nao foi possivel anexar {descricao} ao PDF principal: {str(e)}")
        return pdf_principal


def anexar_pdf_quadro(pdf_planta, pdf_quadro):
    return anexar_pdf_anexo(
        pdf_principal=pdf_planta,
        pdf_anexo=pdf_quadro,
        sufixo_saida='_com_quadro_coordenadas',
        descricao='quadro de coordenadas'
    )


def localizar_python_externo():
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


def gerar_memorial_descritivo_pdf(json_path, numero_reurb_coletivo, pasta_resultados):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    saida_pdf = os.path.join(pasta_resultados, f'memorial_descritivo_{nome_base}.pdf')

    try:
        from gerar_memorial_descritivo import gerar
        return str(gerar(json_path, saida_pdf))
    except Exception as e:
        arcpy.AddWarning(f"Memorial nao gerado diretamente no ArcGIS Python: {str(e)}")

    python_exe = localizar_python_externo()
    if not python_exe:
        arcpy.AddWarning("Python externo nao encontrado; memorial descritivo nao foi gerado automaticamente.")
        return None

    script = os.path.join(os.path.dirname(__file__), 'gerar_memorial_descritivo.py')
    try:
        env = os.environ.copy()
        for chave in ['PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']:
            env.pop(chave, None)
        env['PYTHONNOUSERSITE'] = '1'
        resultado = subprocess.run(
            [python_exe, script, json_path, saida_pdf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            env=env
        )
        if resultado.returncode == 0 and os.path.exists(saida_pdf):
            arcpy.AddMessage(f"Memorial descritivo salvo em: {saida_pdf}")
            return saida_pdf
        arcpy.AddWarning(
            "Memorial descritivo nao gerado via Python externo. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"Memorial descritivo nao gerado via Python externo: {str(e)}")
    return None


def gerar_quadro_areas_pdf(
    numero_reurb_coletivo,
    bairro,
    municipio,
    area_bairro,
    perimetro_bairro,
    fusoutm,
    banda,
    meridiano_central,
    responsavel_tecnico,
    funcao,
    n_crea_cau,
    pasta_resultados
):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    saida_pdf = os.path.join(pasta_resultados, f'quadro_areas_{nome_base}.pdf')
    data_geracao = datetime.now().strftime('%d/%m/%Y')
    payload = {
        'numero_reurb_coletivo': numero_reurb_coletivo,
        'bairro': bairro,
        'municipio': municipio,
        'area_bairro': area_bairro,
        'perimetro_bairro': perimetro_bairro,
        'fusoutm': fusoutm,
        'banda': banda,
        'meridiano_central': meridiano_central,
        'responsavel_tecnico': responsavel_tecnico,
        'funcao': funcao,
        'n_crea_cau': n_crea_cau,
        'data': data_geracao,
        'saida_pdf': saida_pdf,
    }

    try:
        from gerar_quadro_areas import gerar
        return str(gerar(**payload))
    except Exception as e:
        arcpy.AddWarning(f"Quadro de areas nao gerado diretamente no ArcGIS Python: {str(e)}")

    python_exe = localizar_python_externo()
    if not python_exe:
        arcpy.AddWarning("Python externo nao encontrado; quadro de areas nao foi gerado automaticamente.")
        return None

    payload_path = os.path.join(pasta_resultados, f'payload_quadro_areas_{nome_base}.json')
    with open(payload_path, 'w', encoding='utf-8') as arquivo:
        json.dump(payload, arquivo, ensure_ascii=False, indent=2)

    script = os.path.join(os.path.dirname(__file__), 'gerar_quadro_areas.py')
    try:
        env = os.environ.copy()
        for chave in ['PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']:
            env.pop(chave, None)
        env['PYTHONNOUSERSITE'] = '1'
        resultado = subprocess.run(
            [python_exe, script, payload_path, saida_pdf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            env=env
        )
        if resultado.returncode == 0 and os.path.exists(saida_pdf):
            arcpy.AddMessage(f"Quadro de areas salvo em: {saida_pdf}")
            return saida_pdf
        arcpy.AddWarning(
            "Quadro de areas nao gerado via Python externo. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"Quadro de areas nao gerado via Python externo: {str(e)}")
    return None


STATUS_AREAS_TRABALHADAS = {
    0: "Sem status",
    1: "Beneficiário",
    2: "Vago",
    3: "Em análise",
    4: "Beneficiário validado",
    5: "Uso institucional",
    6: "Área pública",
    7: "Área rural",
    8: "Área verde",
    9: "Sistema viário",
    10: "Conflito/pendência",
    11: "Outro",
}


def localizar_lotes_areas_trabalhadas(numero_reurb_coletivo):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    candidatos = [
        Path(r'C:\REURB\SHP').joinpath(f'lotes_{nome_base}.shp'),
        Path(r'C:\REURB\SHP').joinpath(f'lote_{nome_base}.shp'),
    ]
    for candidato in candidatos:
        if arcpy.Exists(str(candidato)):
            return str(candidato)

    servico_lotes = (
        'https://www.arcgis.iterma.ma.gov.br/server/rest/services/'
        'CAMADAS_ITERMA/REURB_ITERMA/FeatureServer/9'
    )
    if arcpy.Exists(servico_lotes):
        return servico_lotes
    return None


def _campo_existente(dataset, candidatos):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(dataset)}
    for candidato in candidatos:
        if candidato.lower() in campos:
            return campos[candidato.lower()]
    return None


def _valor_lote(row, campos, campo):
    if not campo:
        return ''
    return row[campos.index(campo)]


def gerar_quadro_areas_trabalhadas_pdf(
    numero_reurb_coletivo,
    bairro,
    municipio,
    codigo_fuso_bairro,
    pasta_resultados
):
    lotes = localizar_lotes_areas_trabalhadas(numero_reurb_coletivo)
    if not lotes:
        arcpy.AddWarning("Camada de lotes nao encontrada; quadro de areas trabalhadas nao sera gerado.")
        return None

    try:
        from fusos_utm import fusos_utm
    except Exception as e:
        arcpy.AddWarning(f"Nao foi possivel carregar fusos UTM: {str(e)}")
        return None

    nome_base = numero_reurb_coletivo.replace('/', '_')
    saida_pdf = os.path.join(pasta_resultados, f'quadro_areas_trabalhadas_{nome_base}.pdf')
    payload_path = os.path.join(pasta_resultados, f'payload_quadro_areas_trabalhadas_{nome_base}.json')
    workspace = arcpy.env.scratchGDB or arcpy.env.scratchFolder
    if not workspace:
        workspace = pasta_resultados

    try:
        valores = {
            numero_reurb_coletivo,
            numero_reurb_coletivo.replace('_', '/'),
            numero_reurb_coletivo.replace('/', '_')
        }
        campo_n_coletivo = _campo_existente(lotes, ['n_coletivo', 'ncoletivo'])
        where = None
        if campo_n_coletivo:
            where = " OR ".join([f"{arcpy.AddFieldDelimiters(lotes, campo_n_coletivo)} = '{valor}'" for valor in valores])

        camada_lotes = arcpy.management.MakeFeatureLayer(
            lotes,
            f'lotes_areas_trabalhadas_{nome_base.replace("_", "")}',
            where
        )
        quantidade = int(arcpy.management.GetCount(camada_lotes)[0])
        if quantidade == 0:
            arcpy.AddWarning("Nenhum lote encontrado para o processo; quadro de areas trabalhadas nao sera gerado.")
            return None

        lotes_utm = os.path.join(workspace, f'lotes_areas_trabalhadas_utm_{nome_base}')
        if arcpy.Exists(lotes_utm):
            arcpy.management.Delete(lotes_utm)
        arcpy.management.Project(
            in_dataset=camada_lotes,
            out_dataset=lotes_utm,
            out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro])
        )

        campo_quadra = _campo_existente(lotes_utm, ['quadra'])
        campo_lote = _campo_existente(lotes_utm, ['lote'])
        campo_nome = _campo_existente(lotes_utm, ['nome', 'beneficiario', 'beneficiár'])
        campo_cpf = _campo_existente(lotes_utm, ['cpf_cnpj', 'cpf', 'cnpj'])
        campo_status = _campo_existente(lotes_utm, ['status'])

        campos = ['SHAPE@AREA']
        for campo in [campo_quadra, campo_lote, campo_nome, campo_cpf, campo_status]:
            if campo and campo not in campos:
                campos.append(campo)

        linhas = []
        resumo = {}
        with arcpy.da.SearchCursor(lotes_utm, campos) as cursor:
            for row in cursor:
                area = float(row[0] or 0)
                status_valor = _valor_lote(row, campos, campo_status)
                try:
                    status = int(status_valor or 0)
                except Exception:
                    status = 0
                status_nome = STATUS_AREAS_TRABALHADAS.get(status, str(status))
                resumo.setdefault(status, {'status': status, 'status_nome': status_nome, 'quantidade': 0, 'area_m2': 0.0})
                resumo[status]['quantidade'] += 1
                resumo[status]['area_m2'] += area

                linhas.append({
                    'quadra': _valor_lote(row, campos, campo_quadra),
                    'lote': _valor_lote(row, campos, campo_lote),
                    'nome': _valor_lote(row, campos, campo_nome),
                    'cpf_cnpj': _valor_lote(row, campos, campo_cpf),
                    'status': status,
                    'status_nome': status_nome,
                    'area_m2': round(area, 4),
                })

        linhas = sorted(linhas, key=lambda item: (str(item.get('quadra', '')).zfill(8), str(item.get('lote', '')).zfill(8)))
        payload = {
            'numero_reurb_coletivo': numero_reurb_coletivo,
            'bairro': bairro,
            'municipio': municipio,
            'saida_pdf': saida_pdf,
            'resumo_status': sorted(resumo.values(), key=lambda item: item['status']),
            'lotes': linhas,
        }
        with open(payload_path, 'w', encoding='utf-8') as arquivo:
            json.dump(payload, arquivo, ensure_ascii=False, indent=2)
    except Exception as e:
        arcpy.AddWarning(f"Nao foi possivel preparar o quadro de areas trabalhadas: {str(e)}")
        return None

    python_exe = localizar_python_externo()
    if not python_exe:
        arcpy.AddWarning("Python externo nao encontrado; quadro de areas trabalhadas nao foi gerado automaticamente.")
        return None

    script = os.path.join(os.path.dirname(__file__), 'gerar_quadro_areas_trabalhadas.py')
    try:
        env = os.environ.copy()
        for chave in ['PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']:
            env.pop(chave, None)
        env['PYTHONNOUSERSITE'] = '1'
        resultado = subprocess.run(
            [python_exe, script, payload_path, saida_pdf],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=180,
            env=env
        )
        if resultado.returncode == 0 and os.path.exists(saida_pdf):
            arcpy.AddMessage(f"Quadro de areas trabalhadas salvo em: {saida_pdf}")
            return saida_pdf
        arcpy.AddWarning(
            "Quadro de areas trabalhadas nao gerado via Python externo. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"Quadro de areas trabalhadas nao gerado via Python externo: {str(e)}")
    return None


def gerar_quadro_vertices_completo_png(json_path, numero_reurb_coletivo, pasta_resultados):
    nome_base = numero_reurb_coletivo.replace('/', '_')
    saida_png = os.path.join(pasta_resultados, f'quadro_vertices_completo_{nome_base}.png')

    try:
        from gerar_png_quadro_vertices_completo import gerar_por_json
        return str(gerar_por_json(json_path, saida_png))
    except Exception as e:
        arcpy.AddWarning(f"Quadro de vertices completo nao gerado diretamente no ArcGIS Python: {str(e)}")

    python_exe = localizar_python_externo()
    if not python_exe:
        arcpy.AddWarning("Python externo nao encontrado; quadro de vertices completo nao foi gerado automaticamente.")
        return None

    script = os.path.join(os.path.dirname(__file__), 'gerar_png_quadro_vertices_completo.py')
    try:
        env = os.environ.copy()
        for chave in ['PYTHONHOME', 'PYTHONPATH', 'PYTHONUSERBASE', 'CONDA_PREFIX', 'CONDA_DEFAULT_ENV']:
            env.pop(chave, None)
        env['PYTHONNOUSERSITE'] = '1'
        resultado = subprocess.run(
            [python_exe, script, json_path, saida_png],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
            env=env
        )
        if resultado.returncode == 0 and os.path.exists(saida_png):
            arcpy.AddMessage(f"Quadro de vertices completo salvo em: {saida_png}")
            return saida_png
        arcpy.AddWarning(
            "Quadro de vertices completo nao gerado via Python externo. "
            f"Codigo: {resultado.returncode}. Detalhe: {resultado.stderr[:500]}"
        )
    except Exception as e:
        arcpy.AddWarning(f"Quadro de vertices completo nao gerado via Python externo: {str(e)}")
    return None


def registrar_fluxos_json(
    json_final,
    pdf_planta_simplificada,
    pdf_quadro_coordenadas,
    pdf_planta_vertices_memorial,
    pdf_memorial_descritivo,
    pdf_quadro_areas=None,
    pdf_quadro_areas_trabalhadas=None,
    png_quadro_vertices_completo=None
):
    identificacao = json_final['identificacaoPlanilha']
    nome_simplificada = os.path.basename(pdf_planta_simplificada) if pdf_planta_simplificada else ''
    nome_vertices_memorial = os.path.basename(pdf_planta_vertices_memorial) if pdf_planta_vertices_memorial else ''
    nome_memorial = os.path.basename(pdf_memorial_descritivo) if pdf_memorial_descritivo else ''
    nome_quadro = os.path.basename(pdf_quadro_coordenadas) if pdf_quadro_coordenadas else ''
    nome_quadro_areas = os.path.basename(pdf_quadro_areas) if pdf_quadro_areas else ''
    nome_quadro_areas_trabalhadas = os.path.basename(pdf_quadro_areas_trabalhadas) if pdf_quadro_areas_trabalhadas else ''
    identificacao['imagemPlanta'] = arquivo_base64(pdf_planta_simplificada)
    identificacao['imagemPlantaSimplificadaComQuadro'] = arquivo_base64(pdf_planta_simplificada)
    identificacao['imagemPlantaVerticesMemorialComMemorial'] = arquivo_base64(pdf_planta_vertices_memorial)
    identificacao['memorialDescritivo'] = arquivo_base64(pdf_memorial_descritivo)
    identificacao['quadroCoordenadasPlantaSimplificada'] = arquivo_base64(pdf_quadro_coordenadas)
    identificacao['quadroAreas'] = arquivo_base64(pdf_quadro_areas)
    identificacao['quadroAreasTrabalhadas'] = arquivo_base64(pdf_quadro_areas_trabalhadas)
    identificacao['quadroVerticesCompleto'] = arquivo_base64(png_quadro_vertices_completo)
    identificacao['fluxoDocumentos'] = {
        'plantaSimplificada': {
            'tipo': 'planta_simplificada_com_quadro_coordenadas',
            'arquivo': nome_simplificada,
            'anexo': nome_quadro,
            'usaVertices': 'dadosPerimetroPlantaSimplificada',
            'descricao': (
                'Planta grafica simplificada para legibilidade, anexada ao '
                'Quadro de Coordenadas da Planta Simplificada.'
            )
        },
        'plantaVerticesMemorial': {
            'tipo': 'planta_vertices_memorial_com_memorial_descritivo_e_quadro_areas',
            'arquivo': nome_vertices_memorial,
            'anexo': nome_memorial,
            'anexoQuadroAreas': nome_quadro_areas,
            'anexoQuadroAreasTrabalhadas': nome_quadro_areas_trabalhadas,
            'usaVertices': 'dadosPerimetro',
            'descricao': (
                'Planta de conferencia com a sequencia integral de vertices, '
                'anexada ao Memorial Descritivo, ao Quadro de Areas e ao Quadro de Areas Trabalhadas.'
            )
        },
        'referenciaAreaPerimetro': (
            'Area e perimetro impressos correspondem ao perimetro real/completo, '
            'descrito no Memorial Descritivo.'
        )
    }
    return json_final


def slug_resultado(texto):
    texto = str(texto or '').strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^a-z0-9]+', '_', texto).strip('_')
    return texto or 'bairro'


def obter_pasta_resultados_bairro(numero_reurb_coletivo, bairro=''):
    pasta_resultados = os.path.join(os.path.dirname(__file__), 'resultados')
    nome_base = numero_reurb_coletivo.replace('/', '_')
    nome_bairro = slug_resultado(bairro)
    pasta_bairro = os.path.join(pasta_resultados, f'{nome_bairro}_{nome_base}')
    os.makedirs(pasta_bairro, exist_ok=True)
    return pasta_bairro


def copiar_resultado(origem, destino):
    if not origem or not os.path.exists(origem):
        return False
    if os.path.abspath(origem) == os.path.abspath(destino):
        return True
    shutil.copy2(origem, destino)
    return True


def salvar_resultados_visiveis(
    numero_reurb_coletivo,
    json_final,
    pdf_planta,
    zip_lote,
    bairro='',
    pdf_planta_memorial=None,
    pdf_memorial_descritivo=None,
    pdf_quadro_areas=None,
    pdf_quadro_areas_trabalhadas=None
):
    """Salva cópias dos resultados em uma pasta fácil de encontrar."""
    pasta_resultados = obter_pasta_resultados_bairro(numero_reurb_coletivo, bairro)

    nome_base = numero_reurb_coletivo.replace('/', '_')
    pdf_simplificada_saida = os.path.join(pasta_resultados, f'planta_simplificada_com_quadro_{nome_base}.pdf')
    pdf_memorial_saida = os.path.join(pasta_resultados, f'planta_vertices_memorial_com_memorial_{nome_base}.pdf')
    memorial_saida = os.path.join(pasta_resultados, f'memorial_descritivo_{nome_base}.pdf')
    quadro_areas_saida = os.path.join(pasta_resultados, f'quadro_areas_{nome_base}.pdf')
    quadro_areas_trabalhadas_saida = os.path.join(pasta_resultados, f'quadro_areas_trabalhadas_{nome_base}.pdf')
    zip_saida = os.path.join(pasta_resultados, f'shape_{nome_base}.zip')
    json_saida = os.path.join(pasta_resultados, f'resultado_{nome_base}.json')

    copiar_resultado(pdf_planta, pdf_simplificada_saida)
    copiar_resultado(pdf_planta_memorial, pdf_memorial_saida)
    copiar_resultado(pdf_memorial_descritivo, memorial_saida)
    copiar_resultado(pdf_quadro_areas, quadro_areas_saida)
    copiar_resultado(pdf_quadro_areas_trabalhadas, quadro_areas_trabalhadas_saida)
    copiar_resultado(zip_lote, zip_saida)

    with open(json_saida, 'w', encoding='utf-8') as arquivo:
        json.dump(json_final, arquivo, ensure_ascii=False, indent=2)

    arcpy.AddMessage(f"Resultado JSON salvo em: {json_saida}")
    arcpy.AddMessage(f"Planta simplificada com quadro salva em: {pdf_simplificada_saida}")
    if pdf_planta_memorial and os.path.exists(pdf_planta_memorial):
        arcpy.AddMessage(f"Planta com vertices do memorial salva em: {pdf_memorial_saida}")
    if pdf_memorial_descritivo and os.path.exists(pdf_memorial_descritivo):
        arcpy.AddMessage(f"Memorial descritivo salvo em: {memorial_saida}")
    if pdf_quadro_areas and os.path.exists(pdf_quadro_areas):
        arcpy.AddMessage(f"Quadro de areas salvo em: {quadro_areas_saida}")
    if pdf_quadro_areas_trabalhadas and os.path.exists(pdf_quadro_areas_trabalhadas):
        arcpy.AddMessage(f"Quadro de areas trabalhadas salvo em: {quadro_areas_trabalhadas_saida}")
    arcpy.AddMessage(f"Shape ZIP salvo em: {zip_saida}")

    return json_saida, pdf_simplificada_saida, zip_saida

def obter_atributo_bairro(feicao_bairro, numero_reurb_coletivo, campo, padrao=''):
    valores = {
        numero_reurb_coletivo,
        numero_reurb_coletivo.replace('_', '/'),
        numero_reurb_coletivo.replace('/', '_')
    }
    where = " OR ".join([f"n_coletivo = '{valor}'" for valor in valores])
    try:
        campos = {field.name for field in arcpy.ListFields(feicao_bairro)}
        if campo not in campos:
            return padrao
        with arcpy.da.SearchCursor(feicao_bairro, [campo], where) as cursor:
            for row in cursor:
                return row[0] or padrao
    except Exception as e:
        arcpy.AddWarning(f"Nao foi possivel obter {campo} da camada bairro: {str(e)}")
    return padrao

def recarregar_modulos_locais():
    """Força o ArcGIS Pro a usar a versão salva dos módulos locais."""
    modulos = [
        'caminho_camadas',
        'caminhos_gerais',
        'caminho_simbologias',
        'check_reurb_coletivo',
        'check_status',
        'check_responsavel',
        'tabulando_intersecao',
        'exporta_shapefile',
        'municipalidade',
        'transforma_feicao',
        'azminute',
        'formatar_tabela_atributos',
        'exporta_camadas_para_layout',
        'gerar_planta',
        'formatar_json_saida',
        'formatar_dados_perimetro',
        'transforma_vertices_em_linhas',
        'tabela_modelo',
        'normalizacao',
        'exportar_quadro_coordenadas',
        'confrontacao_eixo_viario',
        'simplificar_planta',
        'responsaveis_tecnicos',
    ]
    for modulo in modulos:
        if modulo in sys.modules:
            importlib.reload(sys.modules[modulo])

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Gerar Planta Núcleo"
        self.alias = "GerarPlantaNucleo"

        # List of tool classes associated with this toolbox
        self.tools = []
        self.tools.append(GerarPlantaNucleoTool)

class GerarPlantaNucleoTool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "GerarPlantaNucleoTool"
        self.description = "Ferramenta realiza geração de planta do Núcleo."
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Define the tool parameters."""
        feature_input = arcpy.Parameter(
            name='inputJson',
            displayName='inputJson',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        info_saida = arcpy.Parameter(
            name='outputJson',
            displayName='outputJson',
            direction='Output',
            datatype='GPString',
            parameterType='Derived'
        )
        params = []
        params.append(feature_input)
        params.append(info_saida)
        return params

    def isLicensed(self):
        """Set whether the tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        try:
            recarregar_modulos_locais()
            from caminho_camadas import (
                inicializar_caminhos,
            )
            from tabela_modelo import (
                json_saida_modelo
            )
            from check_reurb_coletivo import check_reurb_coletivo
            from check_status import check_status
            from check_responsavel import check_responsavel_tecnico
            from exporta_shapefile import exporta_shapefile, zipar_shapefile
            from municipalidade import municipalidade
            from transforma_feicao import transforma_feicao
            from azminute import azimute
            from formatar_tabela_atributos import formatar_tabela_atributos
            from exporta_camadas_para_layout import exporta_camadas_para_layout
            from gerar_planta import gerar_planta, exportar_planta_para_pdf
            from formatar_json_saida import formatar_json_saida
            from formatar_dados_perimetro import formatar_dados_perimetro
            from transforma_vertices_em_linhas import transforma_vertices_em_linhas
            from normalizacao import decimal_texto
            from exportar_quadro_coordenadas import exportar_quadro_coordenadas
            from confrontacao_eixo_viario import obter_eixo_viario, filtrar_eixo_confrontante, preencher_confrontantes_por_eixo, transferir_confrontantes_por_segmentos, criar_rotulos_confrontantes
            from simplificar_planta import criar_vertices_segmentos_simplificados
            from responsaveis_tecnicos import resolver_responsavel
        except ImportError as e:
            arcpy.AddError(f"Erro ao importar módulos: {str(e)}")
            raise

        # Inicializar caminhos
        try:
            from caminho_camadas import inicializar_caminhos
        except Exception as e:
            arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
            raise

        try:
            if arcpy.Exists(arcpy.env.scratchGDB):
                arcpy.Delete_management(arcpy.env.scratchGDB)

            scrachgdb = arcpy.env.scratchGDB

            arcpy.AddMessage('Início - Executando comando para obter parâmetros e referencias espaciais')
            json_entrada = ler_input_json(parameters[0].valueAsText)

            bairro = json_entrada['dados'].get('bairro', '')
            # responsavel_tecnico = json_entrada['responsavelTecnico']['nome']
            # formacao = json_entrada['responsavelTecnico']['formacao']
            # codigo_credenciamento = json_entrada['responsavelTecnico']['codigoCredenciamento']
            numero_reurb_coletivo = json_entrada['dados']['numeroProcessoColetivo'].replace('_', '/')
            json_entrada['dados']['numeroProcessoColetivo'] = numero_reurb_coletivo
            forcar_geracao = bool(json_entrada.get('forcarGeracao', False))
            matricula = json_entrada['dados'].get('matricula', '')
            arcpy.AddMessage('Fim - Executando comando para obter parâmetros e referencias espaciais')

            inicializar_caminhos(numero_reurb_coletivo)
            from caminho_camadas import (
                bairro_camada,
                responsavel_tecnico_tabela,
                municipios_camada
            )

            if bairro_camada is None:
                arcpy.AddError("Erro: Caminhos não foram inicializados corretamente")
                raise ValueError("Caminhos não inicializados")

            if not bairro:
                bairro = obter_atributo_bairro(
                    feicao_bairro=bairro_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    campo='nome',
                    padrao=''
                )
                json_entrada['dados']['bairro'] = bairro
            responsavel = resolver_responsavel(json_entrada)
            arcpy.AddMessage(f"Responsável técnico selecionado: {responsavel.get('nome', '')}")

            json_saida = json_saida_modelo

            with arcpy.EnvManager(workspace=scrachgdb, overwriteOutput=True):

                #verificar se o número do REURB coletivo existe
                arcpy.AddMessage('Início - Verificando se o número do REURB coletivo existe')
                reurb_coletivo_existe = check_reurb_coletivo(
                    feicao_bairro=bairro_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo
                )

                if reurb_coletivo_existe is False:
                    json_saida['pronto'] = False
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                arcpy.AddMessage('Fim - Verificando se o número do REURB coletivo existe')

                #verificar o status do bairro
                arcpy.AddMessage('Início - Verificando se o bairro está pronto')
                pronto = check_status(
                    feicao_bairro=bairro_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo
                )

                if pronto is False and forcar_geracao is False:
                    json_saida['pronto'] = pronto
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                elif pronto is False and forcar_geracao is True:
                    arcpy.AddWarning(
                        'Status do bairro não está pronto, mas forcarGeracao=True. '
                        'A geração continuará para teste/local.'
                    )
                arcpy.AddMessage('Fim - Verificando se o bairro está pronto')

                # #verificar se o responsável técnico existe
                # arcpy.AddMessage('Início - Verificando se o responsável técnico existe')
                # responsavel_tecnico_existe, responsavel_tecnico, formacao, codigo_credenciamento = check_responsavel_tecnico(
                #     lote_features=lote_camada,
                #     numero_reurb_coletivo=numero_reurb_coletivo,
                #     quadra=quadra,
                #     lote=lote,
                #     responsavel_tecnico_tabela=responsavel_tecnico_tabela
                # )

                # if responsavel_tecnico_existe is False:
                #     arcpy.AddMessage(f'Responsável técnico {responsavel_tecnico} não cadastrado ou preenchimento incorreto')
                #     json_saida['pronto'] = False
                #     result_json = json.dumps(json_saida, ensure_ascii=False)
                #     arcpy.SetParameter(1, result_json)
                #     return result_json
                # arcpy.AddMessage('Fim - Verificando se o responsável técnico existe')

                #exportar bairro para shapefile, zipar, encontrar fuso utm, calcula area e perimetro
                arcpy.AddMessage('Início - Exportando bairro para shapefile, zipando, encontrando fuso utm, calculando area e perimetro')
                dir_shapefile, bairro_selecionado, codigo_fuso_bairro, banda_utm, meridiano_central, area_bairro, perimetro_bairro = exporta_shapefile(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    feicoes_bairro=bairro_camada
                )
                arcpy.AddMessage('Fim - Exportando bairro para shapefile, zipando, encontrando fuso utm, calculando area e perimetro')
                eixo_viario = obter_eixo_viario()
                eixo_viario_confrontante = filtrar_eixo_confrontante(
                    feicao_perimetro=bairro_selecionado,
                    eixo_viario=eixo_viario
                )
                
                #selecionar municipio de acordo com o bairro
                arcpy.AddMessage('Início - Selecionando municipio de acordo com o bairro')
                municipio, municipio_principal = municipalidade(
                    feicao_perimetro=bairro_selecionado,
                    municipios=municipios_camada,
                    area=area_bairro
                )
                arcpy.AddMessage('Fim - Selecionando municipio de acordo com o bairro')

                #transformar bairro em linha e vertices em pontos
                arcpy.AddMessage('Início - Transformando bairro em linha e vertices em pontos')
                vertices_feicao = transforma_feicao(
                    feicao_perimetro=bairro_selecionado
                )
                arcpy.AddMessage('Fim - Transformando bairro em linha e vertices em pontos')

                #calcular azimute e distancia de cada vertice
                arcpy.AddMessage('Início - Calculando azimute e distancia de cada vertice')
                azimute(
                    feicao_entrada=vertices_feicao
                )
                arcpy.AddMessage('Fim - Calculando azimute e distancia de cada vertice')

                # transforma vertices em linhas
                arcpy.AddMessage('Início - Transformando vertices em linhas')
                confrontantes_bairro = transforma_vertices_em_linhas(
                    vertices_bairro=vertices_feicao
                )                
                arcpy.AddMessage('Fim - Transformando vertices em linhas')

                arcpy.AddMessage('Início - Preenchendo confrontantes pelo eixo viario')
                # Usa o eixo viario completo como fonte principal. O eixo filtrado pode perder
                # logradouros quando o clip/buffer fica restritivo demais para trechos sinuosos.
                eixo_confrontacao = eixo_viario
                confrontantes_bairro = preencher_confrontantes_por_eixo(
                    confrontantes_bairro=confrontantes_bairro,
                    eixo_viario=eixo_confrontacao
                )
                rotulos_confrontantes = criar_rotulos_confrontantes(
                    confrontantes_bairro=confrontantes_bairro
                )
                arcpy.AddMessage('Fim - Preenchendo confrontantes pelo eixo viario')

                #formatar tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N
                arcpy.AddMessage('Início - Formatando tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N')
                confrontantes_bairro_final = formatar_tabela_atributos(
                    feicao_entrada=confrontantes_bairro
                )
                arcpy.AddMessage('Fim - Formatando tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N')

                arcpy.AddMessage('Início - Criando versão simplificada para a prancha principal')
                vertices_planta, confrontantes_planta = criar_vertices_segmentos_simplificados(
                    vertices_bairro=vertices_feicao
                )
                confrontantes_planta = transferir_confrontantes_por_segmentos(
                    confrontantes_destino=confrontantes_planta,
                    confrontantes_referencia=confrontantes_bairro
                )
                confrontantes_planta = preencher_confrontantes_por_eixo(
                    confrontantes_bairro=confrontantes_planta,
                    eixo_viario=eixo_confrontacao
                )
                confrontantes_planta_final = formatar_tabela_atributos(
                    feicao_entrada=confrontantes_planta
                )
                confrontantes_planta_quadro = formatar_tabela_atributos(
                    feicao_entrada=confrontantes_planta,
                    limite_linhas=30
                )
                rotulos_confrontantes_planta = criar_rotulos_confrontantes(
                    confrontantes_bairro=confrontantes_planta
                )
                arcpy.AddMessage('Fim - Criando versão simplificada para a prancha principal')

                #exportar camadas para o layout
                arcpy.AddMessage('Início - Exportando camadas para o layout')
                bairro_layout = exporta_camadas_para_layout(
                    n_reurb_coletivo=numero_reurb_coletivo,
                    bairro_feicoes=bairro_camada
                )
                arcpy.AddMessage('Fim - Exportando camadas para o layout')

                #gerar planta
                arcpy.AddMessage('Início - Gerando planta')
                layout_planta = gerar_planta(
                    bairro_selecionado=bairro_selecionado,
                    confrontantes_bairro=confrontantes_planta_final,
                    vertices_bairro=vertices_planta,
                    eixo_viario=rotulos_confrontantes_planta,
                    tabela_confrontantes=confrontantes_planta_quadro,
                    bairro_layout=bairro_layout,
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    area=decimal_texto(area_bairro),
                    matricula=matricula,
                    folha='01',
                    perimetro=decimal_texto(perimetro_bairro),
                    data=datetime.now().strftime('%d/%m/%Y'),
                    fusoutm=codigo_fuso_bairro,
                    responsavel_tecnico=responsavel.get('nome', ''),
                    funcao=responsavel.get('formacao', ''),
                    n_crea_cau=responsavel.get('registro', ''),
                    tipo_planta='simplificada'
                )
                arcpy.AddMessage('Fim - Gerando planta')

                arcpy.AddMessage('Início - Gerando planta de conferência com vértices do memorial')
                layout_planta_memorial = gerar_planta(
                    bairro_selecionado=bairro_selecionado,
                    confrontantes_bairro=confrontantes_bairro_final,
                    vertices_bairro=vertices_feicao,
                    eixo_viario=rotulos_confrontantes,
                    tabela_confrontantes=confrontantes_bairro_final,
                    bairro_layout=bairro_layout,
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    area=decimal_texto(area_bairro),
                    matricula=matricula,
                    folha='02',
                    perimetro=decimal_texto(perimetro_bairro),
                    data=datetime.now().strftime('%d/%m/%Y'),
                    fusoutm=codigo_fuso_bairro,
                    responsavel_tecnico=responsavel.get('nome', ''),
                    funcao=responsavel.get('formacao', ''),
                    n_crea_cau=responsavel.get('registro', ''),
                    tipo_planta='memorial'
                )
                arcpy.AddMessage('Fim - Gerando planta de conferência com vértices do memorial')

                arcpy.AddMessage('Início - Zipando shapefile')
                zip_lote = zipar_shapefile(
                    dir_shapefile=dir_shapefile
                )
                arcpy.AddMessage('Fim - Zipando shapefile')

                #exportar planta para PDF
                arcpy.AddMessage('Início - Exportando planta para PDF')
                pdf_planta = exportar_planta_para_pdf(
                    layout_planta=layout_planta,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    sufixo='simplificada'
                )
                arcpy.AddMessage('Fim - Exportando planta para PDF')

                arcpy.AddMessage('Início - Exportando planta de conferência para PDF')
                pdf_planta_memorial = exportar_planta_para_pdf(
                    layout_planta=layout_planta_memorial,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    sufixo='vertices_memorial'
                )
                arcpy.AddMessage('Fim - Exportando planta de conferência para PDF')

                #formatar dados perimetro
                arcpy.AddMessage('Início - Formatando dados perimetro')
                dados_perimetro_completo = formatar_dados_perimetro(
                    confrontantes_bairro=confrontantes_bairro_final
                )
                dados_perimetro_planta_simplificada = formatar_dados_perimetro(
                    confrontantes_bairro=confrontantes_planta_final
                )
                pasta_resultados = obter_pasta_resultados_bairro(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    bairro=bairro
                )
                _, _, pdf_quadro_coordenadas = exportar_quadro_coordenadas(
                    dados_perimetro=dados_perimetro_planta_simplificada,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    pasta_resultados=pasta_resultados,
                    responsavel_tecnico=responsavel.get('nome', ''),
                    funcao=responsavel.get('formacao', ''),
                    n_crea_cau=responsavel.get('registro', ''),
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    objetivo='Regularização Fundiária Urbana - REURB'
                )
                pdf_planta = anexar_pdf_quadro(
                    pdf_planta=pdf_planta,
                    pdf_quadro=pdf_quadro_coordenadas
                )
                arcpy.AddMessage('Fim - Formatando dados perimetro')

                #formatar json de saida
                arcpy.AddMessage('Início - Formatando json de saida')
                json_final = formatar_json_saida(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    json_entrada=json_entrada,
                    json_saida=json_saida,
                    dados_perimetro=dados_perimetro_completo,
                    dados_perimetro_planta_simplificada=dados_perimetro_planta_simplificada,
                    pdf_planta=pdf_planta,
                    zip_lote=zip_lote,
                    area_bairro=area_bairro,
                    perimetro_bairro=perimetro_bairro,
                    municipios=municipio,
                    municipios_principal=municipio_principal,
                    fusoutm=codigo_fuso_bairro,
                    meridiano_central=meridiano_central,
                    banda=banda_utm,
                    responsavel_tecnico=responsavel.get('nome', ''),
                    funcao=responsavel.get('formacao', ''),
                    n_crea_cau=responsavel.get('registro', ''),
                    pronto=pronto,
                    pdf_planta_simplificada_com_quadro=pdf_planta,
                    pdf_quadro_coordenadas=pdf_quadro_coordenadas
                )
                nome_base_resultado = numero_reurb_coletivo.replace('/', '_')
                json_intermediario = os.path.join(
                    pasta_resultados,
                    f'resultado_{nome_base_resultado}.json'
                )
                with open(json_intermediario, 'w', encoding='utf-8') as arquivo:
                    json.dump(json_final, arquivo, ensure_ascii=False, indent=2)

                png_quadro_vertices_completo = gerar_quadro_vertices_completo_png(
                    json_path=json_intermediario,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    pasta_resultados=pasta_resultados
                )
                pdf_memorial_descritivo = gerar_memorial_descritivo_pdf(
                    json_path=json_intermediario,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    pasta_resultados=pasta_resultados
                )
                pdf_quadro_areas = gerar_quadro_areas_pdf(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    area_bairro=area_bairro,
                    perimetro_bairro=perimetro_bairro,
                    fusoutm=codigo_fuso_bairro,
                    banda=banda_utm,
                    meridiano_central=meridiano_central,
                    responsavel_tecnico=responsavel.get('nome', ''),
                    funcao=responsavel.get('formacao', ''),
                    n_crea_cau=responsavel.get('registro', ''),
                    pasta_resultados=pasta_resultados
                )
                pdf_quadro_areas_trabalhadas = gerar_quadro_areas_trabalhadas_pdf(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    codigo_fuso_bairro=codigo_fuso_bairro,
                    pasta_resultados=pasta_resultados
                )
                pdf_planta_memorial = anexar_pdf_anexo(
                    pdf_principal=pdf_planta_memorial,
                    pdf_anexo=pdf_memorial_descritivo,
                    sufixo_saida='_com_memorial_descritivo',
                    descricao='memorial descritivo'
                )
                pdf_planta_memorial = anexar_pdf_anexo(
                    pdf_principal=pdf_planta_memorial,
                    pdf_anexo=pdf_quadro_areas,
                    sufixo_saida='_com_quadro_areas',
                    descricao='quadro de areas'
                )
                pdf_planta_memorial = anexar_pdf_anexo(
                    pdf_principal=pdf_planta_memorial,
                    pdf_anexo=pdf_quadro_areas_trabalhadas,
                    sufixo_saida='_com_quadro_areas_trabalhadas',
                    descricao='quadro de areas trabalhadas'
                )
                json_final = registrar_fluxos_json(
                    json_final=json_final,
                    pdf_planta_simplificada=pdf_planta,
                    pdf_quadro_coordenadas=pdf_quadro_coordenadas,
                    pdf_planta_vertices_memorial=pdf_planta_memorial,
                    pdf_memorial_descritivo=pdf_memorial_descritivo,
                    pdf_quadro_areas=pdf_quadro_areas,
                    pdf_quadro_areas_trabalhadas=pdf_quadro_areas_trabalhadas,
                    png_quadro_vertices_completo=png_quadro_vertices_completo
                )
                arcpy.AddMessage('Fim - Formatando json de saida')

                salvar_resultados_visiveis(
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    json_final=json_final,
                    pdf_planta=pdf_planta,
                    zip_lote=zip_lote,
                    bairro=bairro,
                    pdf_planta_memorial=pdf_planta_memorial,
                    pdf_memorial_descritivo=pdf_memorial_descritivo,
                    pdf_quadro_areas=pdf_quadro_areas,
                    pdf_quadro_areas_trabalhadas=pdf_quadro_areas_trabalhadas
                )

                result_json = json.dumps(json_final, ensure_ascii=False)
                arcpy.SetParameter(1, result_json)

                return result_json


        except Exception as e:
            arcpy.AddError(e)
            raise e

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        list(
            map(
                arcpy.Delete_management,
                [arcpy.env.scratchGDB, arcpy.env.scratchFolder]
            )
        )
        return

if __name__ == '__main__':
    # Teste básico de importação
    try:
        import arcpy
        print("ArcPy importado com sucesso")
        
        # Teste de criação da toolbox
        tb = Toolbox()
        print(f"Toolbox criada: {tb.label}")
        
        # Teste de criação da ferramenta
        tool = GerarPlantaNucleoTool()
        print(f"Ferramenta criada: {tool.label}")
        
        # Teste de parâmetros
        params = tool.getParameterInfo()
        print(f"Parâmetros: {len(params)}")
        
        print("✓ Todos os testes passaram!")
    except Exception as e:
        print(f"✗ Erro: {str(e)}")
        import traceback
        traceback.print_exc()

    # class Messenger(object):
    #     def addMessage(self, message):
    #         arcpy.AddMessage(message)

    # input_json = '{"dados": {"numeroProcessoColetivo": "12345", "bairro": "teste", "matricula": "12345"},"responsavelTecnico": "Luciano Schmitter dos Santos"}'
    # # input_json = '{"dados": {"numeroProcessoColetivo": "060503982/2025", "bairro": "teste", "matricula": "12345"},"responsavelTecnico": "Luciano Schmitter dos Santos"}'
    # # input_json = '{"dados": {"numeroProcessoColetivo": "033100029/2026", "bairro": "teste", "matricula": "12345"},"responsavelTecnico": "Luciano Schmitter dos Santos"}'
    # parameters =[]
    # param0 = arcpy.Parameter()
    # param0.value =input_json
    # parameters.append(param0)

    # GerarPlantaNucleo = GerarPlantaNucleoTool()
    # GerarPlantaNucleo.execute(parameters, Messenger())
