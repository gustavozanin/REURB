# -*- coding: utf-8 -*-

import importlib
import json
import sys
import traceback
from pathlib import Path

import arcpy


PASTA_FERRAMENTA = Path(__file__).parent
PASTA_MOTOR = Path(r"C:\REURB\ferramentas\gerarpranchaloteamento")
PASTA_RESULTADOS = PASTA_FERRAMENTA / "resultados"


def preparar_imports():
    for pasta in [str(PASTA_MOTOR), str(PASTA_FERRAMENTA)]:
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
    for modulo in [
        "gerar_prancha_loteamento_arcgis",
        "gerar_memorial_geral",
        "caminhos_gerais",
        "responsaveis_tecnicos",
    ]:
        if modulo in sys.modules:
            importlib.reload(sys.modules[modulo])


def ler_input_json(texto):
    if not texto:
        raise ValueError("inputJson vazio.")
    texto = texto.strip()
    if texto.startswith("'") and texto.endswith("'"):
        texto = texto[1:-1]
    return json.loads(texto)


def preparar_entrada(entrada):
    entrada = dict(entrada or {})
    dados = dict(entrada.get("dados") or {})
    entrada["dados"] = dados
    entrada["tipoPrancha"] = "plantaGeralQuadras"
    entrada.setdefault("eixoViario", r"C:\REURB\SHP\eixo_viario_Peri Mirim.shp")
    entrada.setdefault("pastaSaida", str(PASTA_RESULTADOS / _slug(dados.get("bairro") or entrada.get("bairro") or "bairro")))
    return entrada


def _slug(texto):
    import re
    import unicodedata

    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "_", texto).strip("_").lower()
    return texto or "bairro"


class Toolbox:
    def __init__(self):
        self.label = "Gerar Planta Geral por Bairro"
        self.alias = "GerarPlantaGeralBairro"
        self.tools = [GerarPlantaGeralBairroTool]


class GerarPlantaGeralBairroTool(object):
    def __init__(self):
        self.label = "GerarPlantaGeralBairroTool"
        self.description = "Gera Planta Geral por bairro/nucleo com quadro de quadras e marcacao de frente de lote."
        self.canRunInBackground = True

    def getParameterInfo(self):
        input_json = arcpy.Parameter(
            name="jsonInput",
            displayName="jsonInput",
            direction="Input",
            datatype="GPString",
            parameterType="Required",
        )
        output_json = arcpy.Parameter(
            name="outputJson",
            displayName="outputJson",
            direction="Output",
            datatype="GPString",
            parameterType="Derived",
        )
        return [input_json, output_json]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        try:
            preparar_imports()
            from gerar_prancha_loteamento_arcgis import executar_por_json

            entrada = preparar_entrada(ler_input_json(parameters[0].valueAsText))
            bairro = entrada.get("dados", {}).get("bairro") or entrada.get("bairro") or ""
            arcpy.AddMessage(f"Iniciando Planta Geral por Bairro com frente de lote: {bairro}")
            pdf = executar_por_json(entrada)
            saida = {
                "pronto": True,
                "tipoPrancha": "plantaGeralQuadras",
                "plantaGeralBairro": pdf,
                "pdf": pdf,
            }
            texto_saida = json.dumps(saida, ensure_ascii=False)
            arcpy.SetParameter(1, texto_saida)
            arcpy.AddMessage(f"Planta Geral por Bairro concluida: {pdf}")
            return texto_saida
        except Exception as exc:
            arcpy.AddError(str(exc))
            arcpy.AddError(traceback.format_exc())
            saida = {
                "pronto": False,
                "erro": str(exc),
            }
            texto_saida = json.dumps(saida, ensure_ascii=False)
            try:
                arcpy.SetParameter(1, texto_saida)
            except Exception:
                pass
            raise
