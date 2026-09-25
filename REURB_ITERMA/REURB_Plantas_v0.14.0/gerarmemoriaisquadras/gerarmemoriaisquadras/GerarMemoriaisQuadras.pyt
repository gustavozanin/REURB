# -*- coding: utf-8 -*-
import os
import sys

import arcpy

FEATURESERVER = (
    "https://www.arcgis.iterma.ma.gov.br/server/rest/services/"
    "CAMADAS_ITERMA/REURB_ITERMA/FeatureServer"
)


def _garantir_site_packages_usuario():
    """Expõe pacotes instalados com propy -m pip no processo do ArcGIS Pro."""
    versao = f"Python{sys.version_info.major}{sys.version_info.minor}"
    candidatos = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidatos.append(
            os.path.join(appdata, "Python", versao, "site-packages")
        )
    try:
        import site
        candidatos.append(site.getusersitepackages())
    except Exception:
        pass
    for caminho in candidatos:
        if caminho and os.path.isdir(caminho) and caminho not in sys.path:
            sys.path.insert(0, caminho)


def _importar_execucao_desktop():
    """Carrega execucao_desktop.py da raiz do pacote (chave = caminho)."""
    import hashlib
    import importlib.util
    from importlib.machinery import SourceFileLoader

    raiz = os.path.dirname(os.path.abspath(__file__))
    caminho = None
    for _ in range(8):
        candidato = os.path.join(raiz, "execucao_desktop.py")
        if os.path.isfile(candidato) and os.path.isfile(
            os.path.join(raiz, "VERSAO.txt")
        ):
            caminho = os.path.normpath(os.path.abspath(candidato))
            break
        pai = os.path.dirname(raiz)
        if pai == raiz:
            break
        raiz = pai
    if not caminho:
        raise RuntimeError(
            "Não achei execucao_desktop.py ao lado de VERSAO.txt."
        )
    chave = "reurb_ed_" + hashlib.md5(
        os.path.normcase(caminho).encode("utf-8")
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
        self.label = "Memoriais de Quadras REURB"
        self.alias = "GerarMemoriaisQuadras"
        self.tools = [GerarMemoriaisQuadrasDesktopTool]


class GerarMemoriaisQuadrasDesktopTool:
    def __init__(self):
        self.label = "Gerar Memoriais de Quadras (Desktop)"
        self.description = (
            "Gera um memorial por quadra e um PDF consolidado via FeatureServer."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        def p(nome, rotulo, tipo="GPString", req=False, categoria=None, direcao="Input"):
            x = arcpy.Parameter(
                name=nome,
                displayName=rotulo,
                datatype=tipo,
                direction=direcao,
                parameterType="Required" if req else "Optional",
            )
            if categoria:
                x.category = categoria
            return x

        numero = p("numero_reurb", "Número do REURB coletivo", req=True)
        pasta = p("pasta_saida", "Pasta de saída", "DEFolder", True)
        quadras = p(
            "quadras", "Quadras (separadas por vírgula; vazio = todas)"
        )
        nome = p("nome_rt", "Nome do responsável técnico")
        formacao = p("formacao_rt", "Formação do responsável técnico")
        crea = p("crea_rt", "CREA/CAU do responsável técnico")
        distancia = p(
            "distancia_logradouro_m",
            "Distância máxima do logradouro (m)",
            "GPDouble",
            categoria="Avançado",
        )
        distancia.value = 50.0
        consolidar = p("gerar_consolidado", "Gerar PDF consolidado", "GPBoolean")
        consolidar.value = True
        url = p(
            "featureserver_url",
            "URL do FeatureServer",
            categoria="Avançado",
        )
        url.value = FEATURESERVER
        saida = p("output_json", "Resumo da saída", direcao="Output")
        saida.parameterType = "Derived"
        return [
            numero, pasta, quadras, nome, formacao, crea,
            distancia, consolidar, url, saida,
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        ctx = None
        pasta = os.path.dirname(os.path.abspath(__file__))
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
        _garantir_site_packages_usuario()
        for m in [
            "memorial_quadras_core",
            "documentos_quadras_pdf",
            "fluxo_memoriais_quadras",
        ]:
            sys.modules.pop(m, None)
        try:
            ed = _importar_execucao_desktop()
            numero = parameters[0].valueAsText
            ctx = ed.iniciar_execucao(
                pasta_modulos=pasta,
                pasta_saida_usuario=parameters[1].valueAsText,
                ferramenta="quadras",
                numero_reurb=numero,
                messages=messages,
            )
            from fluxo_memoriais_quadras import executar
            resultado = executar(
                numero,
                ctx.pasta_saida,
                parameters[2].valueAsText or "",
                parameters[3].valueAsText or "",
                parameters[4].valueAsText or "",
                parameters[5].valueAsText or "",
                parameters[8].valueAsText or FEATURESERVER,
                parameters[6].value or 50,
                bool(parameters[7].value),
                messages,
            )
            ctx.finalizar(ok=True)
            arcpy.SetParameterAsText(9, resultado)
            return resultado
        except Exception as e:
            if ctx is not None:
                ctx.finalizar(ok=False, erro=str(e))
            arcpy.AddError(e)
            raise e

    def postExecute(self, parameters):
        return
