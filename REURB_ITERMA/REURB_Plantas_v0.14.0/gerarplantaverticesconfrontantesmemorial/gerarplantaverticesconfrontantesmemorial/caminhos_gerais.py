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

# Nomes dos layouts dentro do project_layout.aprx (ver layout/LEIA-ME_LAYOUTS.txt)
nome_layout_planta = 'Layout_Planta_Perimetro_A3'
nome_layout_memorial = 'Layout_Memorial_Descritivo_A4'
nome_layout_quadro = 'Layout_Quadro_Coordenadas_A4'

output_log = str(
    Path(__file__).\
        parent.\
            joinpath(
                'log'
            )
        )
