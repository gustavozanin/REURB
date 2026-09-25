# -*- coding: utf-8 -*-

from pathlib import Path

try:
    _base_path = Path(__file__).parent.joinpath('layers')
    simbologia_lote = str(_base_path.joinpath('LOTE.lyrx'))
    simbologia_confrontantes = str(_base_path.joinpath('CONFRONTANTES.lyrx'))
    simbologia_vertices = str(_base_path.joinpath('VERTICES.lyrx'))
    simbologia_lote_overview = str(_base_path.joinpath('LOTE_OVERVIEW.lyrx'))
    simbologia_quadra_overview = str(_base_path.joinpath('LOTES_QUADRA_OVERVIEW.lyrx'))
    # Mantido por compatibilidade com módulos herdados do memorial
    simbologia_perimetro_overview = str(_base_path.joinpath('PERIMETRO_OVERVIEW.lyrx'))
except Exception:
    simbologia_lote = None
    simbologia_confrontantes = None
    simbologia_vertices = None
    simbologia_lote_overview = None
    simbologia_quadra_overview = None
    simbologia_perimetro_overview = None
