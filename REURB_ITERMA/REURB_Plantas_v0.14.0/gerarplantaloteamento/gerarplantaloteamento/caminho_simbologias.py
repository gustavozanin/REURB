# -*- coding: utf-8 -*-

from pathlib import Path

try:
    _base_path = Path(__file__).parent.joinpath('layers')

    simbologia_bairro_overview = str(_base_path.joinpath('BAIRRO_OVERVIEW.lyrx'))
    simbologia_quadra = str(_base_path.joinpath('QUADRA.lyrx'))
    simbologia_lote = str(_base_path.joinpath('LOTE.lyrx'))
    simbologia_eixo_viario = str(_base_path.joinpath('EIXO_VIARIO.lyrx'))
except Exception:
    simbologia_bairro = None
    simbologia_bairro_overview = None
    simbologia_quadra = None
    simbologia_lote = None
    simbologia_eixo_viario = None
