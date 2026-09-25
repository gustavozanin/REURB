# -*- coding: utf-8 -*-

from pathlib import Path

json_saida = str(
    Path(__file__).\
        parent.\
            joinpath(
                'json',
                'output.json'
            )
        )

projeto_arcgis = str(
    Path(__file__).\
        parent.\
            joinpath(
                'layout',
                'project_layout.aprx'
            )
        )

layout_mapa = str(
    Path(__file__).\
        parent.\
            joinpath(
                'layout',
                'Layout_Planta_Memorial_A.pagx'
            )
        )

output_log = str(
    Path(__file__).\
        parent.\
            joinpath(
                'log'
            )
        )