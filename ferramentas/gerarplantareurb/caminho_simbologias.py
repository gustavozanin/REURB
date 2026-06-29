# -*- coding: utf-8 -*-

from pathlib import Path

# Construir caminhos das simbologias com tratamento de erro
try:
    _base_path = Path(__file__).parent.joinpath('layers')
    
    simbologia_lote = str(_base_path.joinpath('LOTE.lyrx'))
    simbologia_confrontantes = str(_base_path.joinpath('CONFRONTANTES.lyrx'))
    simbologia_vertices = str(_base_path.joinpath('VERTICES.lyrx'))
    simbologia_lote_overview = str(_base_path.joinpath('LOTE_OVERVIEW.lyrx'))
    simbologia_quadra_overview = str(_base_path.joinpath('LOTES_QUADRA_OVERVIEW.lyrx'))
except Exception as e:
    # Se falhar, define valores None (será tratado durante execução)
    simbologia_lote = None
    simbologia_confrontantes = None
    simbologia_vertices = None
    simbologia_lote_overview = None
    simbologia_quadra_overview = None