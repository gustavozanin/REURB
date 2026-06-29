# -*- coding: utf-8 -*-

from pathlib import Path

json_saida = Path(__file__).\
    parent.\
        joinpath(
            'json',
            'output.json'
        )

json_saida = Path(__file__).\
    parent.\
        joinpath(
            'json',
            'output.json'
        )

projeto_arcgis = Path(__file__).\
    parent.\
        joinpath(
            'layout',
            'project_layout.aprx'
        )
projeto_arcgis = str(projeto_arcgis)

layout_mapa = Path(__file__).\
    parent.\
        joinpath(
            'layout',
            'Layout_Planta_Memorial_A.pagx'
        )
layout_mapa = str(layout_mapa)

output_log = Path(__file__).\
    parent.\
        joinpath(
            'log'
        )
output_log = str(output_log)