# -*- coding: utf-8 -*-

from pathlib import Path

BASE_LOCAL = Path(__file__).parent
BASE_PACOTE = Path(__file__).parents[2].joinpath('cd')

def caminho_local_ou_pacote(*partes):
    caminho_local = BASE_LOCAL.joinpath(*partes)
    if caminho_local.exists():
        return str(caminho_local)
    return str(BASE_PACOTE.joinpath(*partes))

json_saida = caminho_local_ou_pacote('json', 'output.json')

projeto_arcgis = caminho_local_ou_pacote('layout', 'project_layout.aprx')

layout_mapa = caminho_local_ou_pacote('layout', 'Layout_Planta_Memorial_A.pagx')

output_log = str(
    Path(__file__).\
        parent.\
            joinpath(
                'log'
            )
        )
