# -*- coding: utf-8 -*-

import importlib
import json
import sys
import traceback
from pathlib import Path

import arcpy


PASTA_FERRAMENTA = Path(__file__).parent
PASTA_MOTOR = Path(r"C:\REURB\ferramentas\gerarpranchaloteamento")


def preparar_imports():
    for pasta in [str(PASTA_MOTOR), str(PASTA_FERRAMENTA)]:
        if pasta not in sys.path:
            sys.path.insert(0, pasta)
    for modulo in [
        "gerar_memoriais_quadras_bairro",
        "gerar_prancha_loteamento_arcgis",
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


class Toolbox:
    def __init__(self):
        self.label = "Gerar Memoriais de Quadras por Bairro"
        self.alias = "GerarMemoriaisQuadrasBairro"
        self.tools = [GerarMemoriaisQuadrasBairroTool]


class GerarMemoriaisQuadrasBairroTool(object):
    def __init__(self):
        self.label = "GerarMemoriaisQuadrasBairroTool"
        self.description = "Exporta as camadas atuais do ArcGIS Pro e gera um PDF de memorial descritivo para cada quadra do bairro."
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
            from gerar_memoriais_quadras_bairro import gerar_memoriais_por_json

            entrada = ler_input_json(parameters[0].valueAsText)
            dados = entrada.get("dados", {}) or {}
            bairro = dados.get("bairro") or entrada.get("bairro") or ""
            arcpy.AddMessage(f"Iniciando memoriais descritivos das quadras: {bairro}")
            saida = gerar_memoriais_por_json(entrada)
            texto_saida = json.dumps(saida, ensure_ascii=False)
            arcpy.SetParameter(1, texto_saida)
            arcpy.AddMessage(f"Memoriais de quadras concluidos: {saida.get('pastaSaida')}")
            arcpy.AddMessage(f"PDFs gerados: {saida.get('quantidadeQuadras')}")
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
