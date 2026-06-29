# -*- coding: utf-8 -*-

import importlib
import json
import sys
import traceback

import arcpy


def recarregar_modulos_locais():
    for modulo in [
        "gerar_prancha_loteamento_arcgis",
        "gerar_prancha_loteamento",
        "caminhos_gerais",
    ]:
        if modulo in sys.modules:
            importlib.reload(sys.modules[modulo])


class Toolbox:
    def __init__(self):
        self.label = "Gerar Prancha Loteamento"
        self.alias = "GerarPranchaLoteamento"
        self.tools = [GerarPranchaLoteamentoTool]


class GerarPranchaLoteamentoTool(object):
    def __init__(self):
        self.label = "GerarPranchaLoteamentoTool"
        self.description = "Gera Prancha 02 - Planta do Loteamento no layout do ArcGIS e Lista de Beneficiarios."
        self.canRunInBackground = True

    def getParameterInfo(self):
        input_json = arcpy.Parameter(
            name="inputJson",
            displayName="inputJson",
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
            recarregar_modulos_locais()
            from gerar_prancha_loteamento_arcgis import executar_por_json, ler_input_json

            entrada = ler_input_json(parameters[0].valueAsText)
            arcpy.AddMessage("Iniciando geracao da Prancha 02 - Planta do Loteamento no ArcGIS.")
            pdf = executar_por_json(entrada)
            saida = {
                "pronto": True,
                "prancha02ArcGIS": pdf,
            }
            texto_saida = json.dumps(saida, ensure_ascii=False)
            arcpy.SetParameter(1, texto_saida)
            arcpy.AddMessage(f"Prancha 02 concluida: {pdf}")
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
