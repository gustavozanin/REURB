# -*- coding: utf-8 -*-

import json
import os
import sys
import arcpy

FEATURESERVER_URL_PADRAO = (
    'https://www.arcgis.iterma.ma.gov.br/server/rest/services/'
    'CAMADAS_ITERMA/REURB_ITERMA/FeatureServer'
)

_MODULOS_LOCAIS = (
    'preparar_ambiente',
    'caminho_camadas',
    'fluxo_geracao',
    'exporta_shapefile',
    'exporta_camadas_para_layout',
    'salvar_artefatos_desktop',
    'check_responsavel',
    'check_reurb_coletivo',
    'check_status',
    'gerar_planta',
    'formatar_json_saida',
    'municipalidade',
    'tabela_quadras',
    'tabela_anexo_lotes',
    'tabela_modelo',
    'caminho_simbologias',
    'caminhos_gerais',
    'fusos_utm',
    'tabulando_intersecao',
    'logger',
)


def _ativar_pasta_desta_toolbox():
    """Garante imports desta pasta (não da ferramenta Núcleo)."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    limpos = []
    for p in sys.path:
        pl = p.replace('\\', '/').lower()
        if 'gerarplantanucleo' in pl or 'gerarplantaloteamento' in pl:
            continue
        limpos.append(p)
    sys.path[:] = limpos
    sys.path.insert(0, pasta)
    for nome in _MODULOS_LOCAIS:
        sys.modules.pop(nome, None)
    return pasta


def _importar_execucao_desktop():
    """Carrega execucao_desktop.py da raiz do pacote (chave = caminho)."""
    import hashlib
    import importlib.util
    from importlib.machinery import SourceFileLoader

    raiz = os.path.dirname(os.path.abspath(__file__))
    caminho = None
    for _ in range(8):
        candidato = os.path.join(raiz, 'execucao_desktop.py')
        if os.path.isfile(candidato) and os.path.isfile(
            os.path.join(raiz, 'VERSAO.txt')
        ):
            caminho = os.path.normpath(os.path.abspath(candidato))
            break
        pai = os.path.dirname(raiz)
        if pai == raiz:
            break
        raiz = pai
    if not caminho:
        raise RuntimeError(
            'Não achei execucao_desktop.py ao lado de VERSAO.txt.'
        )
    chave = 'reurb_ed_' + hashlib.md5(
        os.path.normcase(caminho).encode('utf-8')
    ).hexdigest()[:16]
    if chave in sys.modules:
        return sys.modules[chave]
    loader = SourceFileLoader(chave, caminho)
    spec = importlib.util.spec_from_loader(chave, loader)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[chave] = modulo
    loader.exec_module(modulo)
    return modulo


class Toolbox:
    def __init__(self):
        self.label = "Gerar Planta Loteamento"
        self.alias = "GerarPlantaLoteamento"
        self.tools = [
            GerarPlantaLoteamentoTool,
            GerarPlantaLoteamentoDesktopTool,
        ]


class GerarPlantaLoteamentoTool(object):
    """Ferramenta geoserviço: inputJson / outputJson (modo SDE)."""

    def __init__(self):
        self.label = "GerarPlantaLoteamentoTool"
        self.description = "Ferramenta realiza geração de planta do Loteamento."
        self.canRunInBackground = True

    def getParameterInfo(self):
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
        return [feature_input, info_saida]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        try:
            _ativar_pasta_desta_toolbox()
            from fluxo_geracao import executar_geracao_loteamento
        except ImportError as e:
            arcpy.AddError(f"Erro ao importar módulos: {str(e)}")
            raise

        try:
            json_entrada = json.loads(parameters[0].valueAsText.replace("'", ""))
            numero_reurb_coletivo = json_entrada['numeroProcessoColetivo']
            result_json = executar_geracao_loteamento(
                numero_reurb_coletivo=numero_reurb_coletivo,
                messages=messages,
                modo='SDE',
            )
            arcpy.SetParameter(1, result_json)
            return result_json
        except Exception as e:
            arcpy.AddError(e)
            raise e

    def postExecute(self, parameters):
        return


class GerarPlantaLoteamentoDesktopTool(object):
    """Ferramenta Desktop: nº REURB + pasta de saída + FeatureServer."""

    def __init__(self):
        self.label = "Gerar Planta Loteamento (Desktop)"
        self.description = (
            "Gera a planta de loteamento via FeatureServer e salva PDF/ZIP "
            "na pasta escolhida. Não requer VPN/SDE."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        numero = arcpy.Parameter(
            name='numero_reurb',
            displayName='Número do REURB coletivo',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        pasta = arcpy.Parameter(
            name='pasta_saida',
            displayName='Pasta de saída (PDF e ZIP)',
            direction='Input',
            datatype='DEFolder',
            parameterType='Required'
        )

        url_fs = arcpy.Parameter(
            name='featureserver_url',
            displayName='URL do FeatureServer (avançado)',
            direction='Input',
            datatype='GPString',
            parameterType='Optional'
        )
        url_fs.value = FEATURESERVER_URL_PADRAO

        nome_rt = arcpy.Parameter(
            name='nome_override',
            displayName='Nome do RT (se vazio no Bairro)',
            direction='Input',
            datatype='GPString',
            parameterType='Optional'
        )

        formacao = arcpy.Parameter(
            name='formacao_override',
            displayName='Formação do RT (opcional)',
            direction='Input',
            datatype='GPString',
            parameterType='Optional'
        )

        crea = arcpy.Parameter(
            name='credenciamento_override',
            displayName='CREA/CAU do RT (opcional)',
            direction='Input',
            datatype='GPString',
            parameterType='Optional'
        )

        info_saida = arcpy.Parameter(
            name='outputJson',
            displayName='Resumo da saída',
            direction='Output',
            datatype='GPString',
            parameterType='Derived'
        )

        return [numero, pasta, url_fs, nome_rt, formacao, crea, info_saida]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        ctx = None
        try:
            pasta = _ativar_pasta_desta_toolbox()
            ed = _importar_execucao_desktop()
            numero = parameters[0].valueAsText.strip() if parameters[0].valueAsText else ''
            ctx = ed.iniciar_execucao(
                pasta_modulos=pasta,
                pasta_saida_usuario=parameters[1].valueAsText,
                ferramenta='loteamento',
                numero_reurb=numero,
                messages=messages,
            )
            from fluxo_geracao import executar_geracao_loteamento
            url_fs = parameters[2].valueAsText or FEATURESERVER_URL_PADRAO
            result_json = executar_geracao_loteamento(
                numero_reurb_coletivo=numero,
                messages=messages,
                pasta_saida=ctx.pasta_saida,
                modo='FEATURESERVER',
                featureserver_url=url_fs,
                nome_override=parameters[3].valueAsText,
                formacao_override=parameters[4].valueAsText,
                credenciamento_override=parameters[5].valueAsText,
                contexto=ctx,
            )
            ctx.finalizar(ok=True)
            arcpy.SetParameter(6, result_json)
            return result_json
        except Exception as e:
            if ctx is not None:
                ctx.finalizar(ok=False, erro=str(e))
            arcpy.AddError(e)
            raise e

    def postExecute(self, parameters):
        return


if __name__ == '__main__':
    try:
        tb = Toolbox()
        print(f"Toolbox criada: {tb.label}")
        tool = GerarPlantaLoteamentoDesktopTool()
        print(f"Ferramenta Desktop: {tool.label}")
        print(f"Parâmetros: {len(tool.getParameterInfo())}")
        print("Testes básicos ok")
    except Exception as e:
        print(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()
