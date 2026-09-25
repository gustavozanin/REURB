# -*- coding: utf-8 -*-

from pathlib import Path

# Construir caminhos das simbologias com tratamento de erro
try:
    _base_path = Path(__file__).parent.joinpath('layers')
    simbologia_confrontantes = str(_base_path.joinpath('CONFRONTANTES.lyrx'))
    simbologia_vertices = str(_base_path.joinpath('VERTICES.lyrx'))
    simbologia_perimetro_overview = str(_base_path.joinpath('PERIMETRO_OVERVIEW.lyrx'))
except Exception:
    simbologia_confrontantes = None
    simbologia_vertices = None
    simbologia_perimetro_overview = None
