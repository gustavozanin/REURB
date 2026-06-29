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


def main():
    arcpy.env.overwriteOutput = True

    input_json = {
        "dados": {
            "numeroProcessoColetivo": "050601273/2026",
            "bairro": "Centro",
            "matricula": ""
        },
        "responsavelTecnico": "leandro_miranda_da_silva",
        "forcarGeracao": True
    }

    tool = carregar_toolbox()
    resultado = tool.execute([ParametroTexto(json.dumps(input_json, ensure_ascii=False))], None)

    saida = Path(__file__).parent.joinpath("json", "resultado_050601273_2026.json")
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(resultado, encoding="utf-8")

    arcpy.AddMessage(f"Resultado salvo em: {saida}")
    print(f"Resultado salvo em: {saida}")


if __name__ == "__main__":
    main()
