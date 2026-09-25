# -*- coding: utf-8 -*-

import arcpy
from pathlib import Path
import os

sirgas2000 = arcpy.SpatialReference(4674)

# Permite configurar o caminho da conexão .sde via variável de ambiente
_env_sde = os.environ.get('SDE_CONNECTION_FILE')
if _env_sde and Path(_env_sde).exists():
    input_geo_database = str(Path(_env_sde))
else:
    input_geo_database = Path(__file__).\
        parents[2].\
            joinpath(
                'Bases',
                'sicarf_ap_geo.sde'
            )
    input_geo_database = str(input_geo_database)