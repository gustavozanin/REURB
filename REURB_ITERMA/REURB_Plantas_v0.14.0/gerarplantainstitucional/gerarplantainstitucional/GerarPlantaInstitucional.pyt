# -*- coding: utf-8 -*-

import os
import sys
import arcpy

FEATURESERVER_URL_PADRAO = (
    'https://www.arcgis.iterma.ma.gov.br/server/rest/services/'
    'CAMADAS_ITERMA/REURB_ITERMA/FeatureServer'
)

DENSIDADES = ['integral', 'simplificado']

_MODULOS_LOCAIS = (
    'preparar_ambiente',
    'caminho_camadas',
    'fluxo_geracao',
    'exporta_shapefile',
    'salvar_artefatos_desktop',
    'check_responsavel',
    'check_reurb_coletivo',
    'check_status',
    'check_lote_institucional',
    'dominio_status_lote',
    'municipalidade',
    'tabela_modelo',
    'caminho_simbologias',
    'caminhos_gerais',
    'fusos_utm',
    'tabulando_intersecao',
    'confrontantes',
    'constantes',
    'transforma_feicao',
    'transforma_vertices_em_linhas',
    'formatar_tabela_atributos',
    'formatar_dados_perimetro',
    'variaveis_globais',
    'logger',
    'simplificar_vertices',
    'azimute_utm',
    'motor_perimetro',
    'autenticacao_documentos',
    'documentos_pdf',
    'pipeline_perimetro',
    'quadro_coordenadas',
    'memorial_narrativo',
    'gerar_planta_perimetro',
    'gerar_planta_institucional',
    'exportar_pdf_unificado',
    'linearizar_arcos',
)


def _garantir_site_packages_usuario():
    """Inclui o site-packages do usuário (ex.: reportlab via pip)."""
    ver = f'Python{sys.version_info.major}{sys.version_info.minor}'
    candidatos = []
    appdata = os.environ.get('APPDATA')
    if appdata:
        candidatos.append(os.path.join(appdata, 'Python', ver, 'site-packages'))
    try:
        import site
        candidatos.append(site.getusersitepackages())
    except Exception:
        pass
    for pasta_user in candidatos:
        if pasta_user and os.path.isdir(pasta_user) and pasta_user not in sys.path:
            sys.path.insert(0, pasta_user)


def _ativar_pasta_desta_toolbox():
    """Garante imports desta pasta (não das outras ferramentas do pacote)."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    limpos = []
    for p in sys.path:
        pl = p.replace('\\', '/').lower()
        if (
            'gerarplantanucleo' in pl
            or 'gerarplantaloteamento' in pl
            or 'gerarplantaverticesconfrontantesmemorial' in pl
            or 'gerarmemoriaisquadras' in pl
            or 'gerarplantainstitucional' in pl
        ):
            continue
        limpos.append(p)
    sys.path[:] = limpos
    sys.path.insert(0, pasta)
    _garantir_site_packages_usuario()
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
        self.label = "Gerar Planta Lote Institucional"
        self.alias = "GerarPlantaInstitucional"
        self.tools = [
            GerarPlantaInstitucionalDesktopTool,
        ]


class GerarPlantaInstitucionalDesktopTool(object):
    """Ferramenta Desktop: planta + memorial + quadro de imóvel institucional.

    Identificação: n_coletivo + quadra + lote. Status: Institucional Municipal
    ou Institucional Estadual. Ver .specs/features/gerarplantainstitucional/
    """

    def __init__(self):
        self.label = "Gerar Planta Lote Institucional (Desktop)"
        self.description = (
            "Gera PDF unificado (planta + memorial + quadro) de um lote "
            "institucional via FeatureServer (REURB + quadra + lote). "
            "Não requer VPN/SDE."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        numero = arcpy.Parameter(
            name='numero_reurb',
            displayName='Número do REURB coletivo',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )
        numero.value = ''

        quadra = arcpy.Parameter(
            name='quadra',
            displayName='Quadra',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        lote = arcpy.Parameter(
            name='lote',
            displayName='Lote',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        pasta = arcpy.Parameter(
            name='pasta_saida',
            displayName='Pasta de saída (PDF, CSV e ZIP)',
            direction='Input',
            datatype='DEFolder',
            parameterType='Required'
        )

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

        densidade = arcpy.Parameter(
            name='densidade',
            displayName='Densidade de vértices',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )
        densidade.filter.type = 'ValueList'
        densidade.filter.list = DENSIDADES
        densidade.value = 'integral'

        url_fs = arcpy.Parameter(
            name='featureserver_url',
            displayName='URL do FeatureServer (avançado)',
            direction='Input',
            datatype='GPString',
            parameterType='Optional',
            category='Avançado'
        )
        url_fs.value = FEATURESERVER_URL_PADRAO

        tolerancia = arcpy.Parameter(
            name='tolerancia_m',
            displayName='Tolerância da simplificação (m, avançado)',
            direction='Input',
            datatype='GPDouble',
            parameterType='Optional',
            category='Avançado'
        )
        tolerancia.value = 0.5

        info_saida = arcpy.Parameter(
            name='outputJson',
            displayName='Resumo da saída',
            direction='Output',
            datatype='GPString',
            parameterType='Derived'
        )

        return [
            numero,
            quadra,
            lote,
            pasta,
            nome_rt,
            formacao,
            crea,
            densidade,
            url_fs,
            tolerancia,
            info_saida,
        ]

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
            quadra = parameters[1].valueAsText.strip() if parameters[1].valueAsText else ''
            lote = parameters[2].valueAsText.strip() if parameters[2].valueAsText else ''
            ctx = ed.iniciar_execucao(
                pasta_modulos=pasta,
                pasta_saida_usuario=parameters[3].valueAsText,
                ferramenta='institucional',
                numero_reurb=numero,
                messages=messages,
            )
            ctx.diagnostico['quadra'] = quadra
            ctx.diagnostico['lote'] = lote
            from fluxo_geracao import executar_geracao_institucional
            result_json = executar_geracao_institucional(
                numero_reurb_coletivo=numero,
                quadra=quadra,
                lote=lote,
                pasta_saida=ctx.pasta_saida,
                messages=messages,
                featureserver_url=parameters[8].valueAsText or FEATURESERVER_URL_PADRAO,
                nome_override=parameters[4].valueAsText,
                formacao_override=parameters[5].valueAsText,
                credenciamento_override=parameters[6].valueAsText,
                densidade=parameters[7].valueAsText or 'integral',
                tolerancia_m=parameters[9].value if parameters[9].value is not None else 0.5,
            )
            ctx.finalizar(ok=True)
            arcpy.SetParameter(10, result_json)
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
        tool = GerarPlantaInstitucionalDesktopTool()
        print(f"Ferramenta Desktop: {tool.label}")
        nomes = [p.name for p in tool.getParameterInfo()]
        print(f"Parâmetros ({len(nomes)}): {nomes}")
        assert 'quadra' in nomes and 'lote' in nomes
        print("Testes básicos ok")
    except Exception as e:
        print(f"Erro: {str(e)}")
        import traceback
        traceback.print_exc()