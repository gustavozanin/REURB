# -*- coding: utf-8 -*-

import importlib
import json
import sys
import traceback

import arcpy


def recarregar_modulos_locais():
    for modulo in [
        "gerar_prancha_andamento_reurb",
    ]:
        if modulo in sys.modules:
            importlib.reload(sys.modules[modulo])


class Toolbox:
    def __init__(self):
        self.label = "Gerar Prancha Andamento REURB"
        self.alias = "GerarPranchaAndamentoREURB"
        self.tools = [GerarPranchaAndamentoREURBTool]


class GerarPranchaAndamentoREURBTool(object):
    def __init__(self):
        self.label = "GerarPranchaAndamentoREURBTool"
        self.description = "Gera a Prancha Andamento REURB na etapa de Pre-vetorizacao usando as camadas atuais do ArcGIS Pro."
        self.canRunInBackground = True

    def getParameterInfo(self):
        input_json = arcpy.Parameter(
            name="inputJson",
            displayName="inputJson ou caminho do JSON",
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
        parameters[0].clearMessage()
        texto = parameters[0].valueAsText
        if not texto or not str(texto).strip():
            parameters[0].setErrorMessage("Informe o inputJson ou o caminho do arquivo JSON.")
            return
        try:
            recarregar_modulos_locais()
            from gerar_prancha_andamento_reurb import ler_input_json

            entrada = ler_input_json(texto)
            itens = entrada.get("coletivos") if isinstance(entrada, dict) and "coletivos" in entrada else [entrada]
            for item in itens:
                dados = item.get("dados") or {}
                if not dados.get("numeroProcessoColetivo"):
                    parameters[0].setWarningMessage("Falta dados.numeroProcessoColetivo em um item.")
                    return
                if not dados.get("bairro"):
                    parameters[0].setWarningMessage("Falta dados.bairro em um item.")
                    return
        except Exception as exc:
            parameters[0].setErrorMessage(f"inputJson invalido: {exc}")

    def execute(self, parameters, messages):
        try:
            recarregar_modulos_locais()
            from gerar_prancha_andamento_reurb import executar_por_json, ler_input_json

            entrada = ler_input_json(parameters[0].valueAsText)
            arcpy.AddMessage("Iniciando geracao da Prancha Andamento REURB.")
            resultado = executar_por_json(entrada)
            saida = {
                "pronto": True,
                "resultado": "Prancha Andamento REURB",
            }
            if isinstance(resultado, dict):
                saida.update(resultado)
            else:
                saida["pdf"] = resultado
            texto_saida = json.dumps(saida, ensure_ascii=False)
            arcpy.SetParameter(1, texto_saida)
            arcpy.AddMessage("Prancha Andamento REURB concluida.")
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
