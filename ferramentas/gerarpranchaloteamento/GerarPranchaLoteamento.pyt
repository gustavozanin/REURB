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
        "responsaveis_tecnicos",
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
        parameters[0].clearMessage()
        texto = parameters[0].valueAsText
        if not texto or not str(texto).strip():
            parameters[0].setErrorMessage("Informe o inputJson.")
            return
        try:
            recarregar_modulos_locais()
            from gerar_prancha_loteamento_arcgis import ler_input_json

            entrada = ler_input_json(texto)
            dados = entrada.get("dados") or {}
            if not dados.get("numeroProcessoColetivo"):
                parameters[0].setWarningMessage("Falta dados.numeroProcessoColetivo.")
            elif not dados.get("bairro"):
                parameters[0].setWarningMessage("Falta dados.bairro.")
            elif entrada.get("exportarCamadasArcGIS") and not entrada.get("aprxCamadas"):
                parameters[0].setWarningMessage("Informe aprxCamadas ou camadas com o caminho do APRX.")
        except Exception as exc:
            parameters[0].setErrorMessage(f"inputJson invalido: {exc}")

    def execute(self, parameters, messages):
        try:
            recarregar_modulos_locais()
            from gerar_prancha_loteamento_arcgis import executar_por_json, ler_input_json

            entrada = ler_input_json(parameters[0].valueAsText)
            tipo_prancha = str(entrada.get("tipoPrancha") or entrada.get("dados", {}).get("tipoPrancha") or "").strip()
            if tipo_prancha:
                arcpy.AddMessage(f"Iniciando geracao da prancha '{tipo_prancha}' no ArcGIS.")
            else:
                arcpy.AddMessage("Iniciando geracao da Prancha 02 - Planta do Loteamento no ArcGIS.")
            resultado = executar_por_json(entrada)
            pdf = resultado.get("plantaGeralMunicipio") if isinstance(resultado, dict) else resultado
            saida = {
                "pronto": True,
                "pdf": pdf,
            }
            if isinstance(resultado, dict):
                saida.update(resultado)
            if tipo_prancha:
                saida["tipoPrancha"] = tipo_prancha
            else:
                saida["prancha02ArcGIS"] = pdf
            texto_saida = json.dumps(saida, ensure_ascii=False)
            arcpy.SetParameter(1, texto_saida)
            arcpy.AddMessage(f"Prancha concluida: {pdf}")
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
