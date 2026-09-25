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

# Nomes dos layouts dentro do project_layout.aprx
# Planta: padrão lote individual (gerarplantareurb / Layout_Planta_Memorial_A)
nome_layout_planta = 'Layout_Planta_Memorial_A'
# Memorial/quadro: gerados por ReportLab (documentos_pdf), não exigem layout A4
nome_layout_memorial = 'Layout_Memorial_Descritivo_A4'
nome_layout_quadro = 'Layout_Quadro_Coordenadas_A4'

output_log = str(
    Path(__file__).\
        parent.\
            joinpath(
                'log'
            )
        )
