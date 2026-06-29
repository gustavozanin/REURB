# -*- coding: utf-8 -*-

import importlib.machinery
import importlib.util
import json
from pathlib import Path

import arcpy


class ParametroTexto:
    def __init__(self, value):
        self.valueAsText = value


def carregar_toolbox():
    caminho_pyt = Path(__file__).with_name("GerarPlantaNucleo.pyt")
    loader = importlib.machinery.SourceFileLoader("GerarPlantaNucleo", str(caminho_pyt))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    modulo = importlib.util.module_from_spec(spec)
    loader.exec_module(modulo)
    return modulo.GerarPlantaNucleoTool()


def executar(tool, input_json, nome_saida):
    arcpy.AddMessage(f"Iniciando geracao local normalizada: {nome_saida}")
    resultado = tool.execute([ParametroTexto(json.dumps(input_json, ensure_ascii=False))], None)

    saida = Path(__file__).parent.joinpath("json", nome_saida)
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(resultado, encoding="utf-8")

    arcpy.AddMessage(f"JSON salvo em: {saida}")
    print(f"JSON salvo em: {saida}")


def main():
    arcpy.env.overwriteOutput = True
    tool = carregar_toolbox()

    processos = [
        (
            {
                "dados": {
                    "numeroProcessoColetivo": "051201571/2026",
                    "bairro": "",
                    "matricula": ""
                },
                "responsavelTecnico": ""
            },
            "resultado_local_normalizado_051201571_2026.json"
        ),
        (
            {
                "dados": {
                    "numeroProcessoColetivo": "050601273/2026",
                    "bairro": "",
                    "matricula": ""
                },
                "responsavelTecnico": "",
                "forcarGeracao": True
            },
            "resultado_local_normalizado_050601273_2026.json"
        )
    ]

    for input_json, nome_saida in processos:
        executar(tool, input_json, nome_saida)


if __name__ == "__main__":
    main()
