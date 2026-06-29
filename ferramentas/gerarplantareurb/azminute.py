import arcpy
import math

def az_quad(
    delta_x: float,
    delta_y: float
) -> float:
    """
    Calcula o azimute de um segmento de reta em graus decimal.

    -----
    Args:
        delta_x(float):
            Diferença de coordenadas x entre dois pontos.
        delta_y(float):
            Diferença de coordenadas y entre dois pontos.

    -----
    Returns:
        az(float):
            Azimute em graus decimal.
    """
    az = math.degrees(math.atan2(delta_x, delta_y))

    if az < 0:
        az = 360 + az

    return az

def azimute_grau_minuto_segundo(
    az: float
) -> str:
    """
    Converte o azimute em graus decimal para graus, minutos e segundos.

    -----
    Args:
        az(float):
            Azimute em graus decimal.

    -----
    Returns:
        az_grau_minuto_segundo(str):
            Azimute em graus, minutos e segundos.
    """
    graus = int(az)
    minutos_flutuantes = (az - graus) * 60
    minutos = int(minutos_flutuantes)
    segundos = (minutos_flutuantes - minutos) * 60
    segundos = round(segundos, 2)
    
    az_grau_minuto_segundo = f'{graus}° {minutos}′ {segundos}″'

    return az_grau_minuto_segundo

def azimute(
    in_features: str
) -> None:
    """
    Calcula o azimute de um segmento de reta em graus decimal e adiciona as colunas E, N e azimute ao shapefile de entrada.

    -----
    Args:
        in_features(str):
            Caminho para o shapefile de entrada.

    -----
    Returns:
        None
    """
    arcpy.AddFields_management(
        in_table=in_features,
        field_description=[
            ['E', 'DOUBLE', 'E'],
            ['N', 'DOUBLE', 'N'],
            ['azimute', 'TEXT', 'azimute']
        ]
    )

    cursor = arcpy.da.SearchCursor(in_features, ['OBJECTID', 'SHAPE@X', 'SHAPE@Y'])
    dict_coord = {row[0]: [row[1], row[2]] for row in cursor}
    print(dict_coord)

    with arcpy.da.SearchCursor(in_features, ['OBJECTID']) as cursor:
        for row in cursor:
            oid = row[0]
            print(oid)
            if oid < list(dict_coord.keys())[-2]:
                delt_x = dict_coord[oid+1][0] - dict_coord[oid][0]
                print(delt_x)
                
                delt_y = dict_coord[oid+1][1] - dict_coord[oid][1]
                print(delt_y)

                az = az_quad(delt_x, delt_y)
                print(az)

                az_grau_minuto_segundo = azimute_grau_minuto_segundo(
                    az=az
                )
                print(az_grau_minuto_segundo)

                arcpy.CalculateFields_management(
                    in_table=in_features,
                    expression_type='PYTHON3',
                    fields=[
                        ['E', str(dict_coord[oid][0]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['N', str(dict_coord[oid][1]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['azimute', f'\'{az_grau_minuto_segundo}\'', f'OBJECTID = {oid}']
                    ]
                )

            elif oid == list(dict_coord.keys())[-2]:
                delt_x = dict_coord[1][0] - dict_coord[oid][0]
                print(delt_x)
                
                delt_y = dict_coord[1][1] - dict_coord[oid][1]
                print(delt_y)

                az = az_quad(delt_x, delt_y)
                print(az)

                az_grau_minuto_segundo = azimute_grau_minuto_segundo(
                    az=az
                )
                print(az_grau_minuto_segundo)

                arcpy.CalculateFields_management(
                    in_table=in_features,
                    expression_type='PYTHON3',
                    fields=[
                        ['E', str(dict_coord[oid][0]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['N', str(dict_coord[oid][1]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['azimute', f'\'{az_grau_minuto_segundo}\'', f'OBJECTID = {oid}']
                    ]
                )

            else:
                az = 0
                arcpy.CalculateFields_management(
                    in_table=in_features,
                    expression_type='PYTHON3',
                    fields=[
                        ['E', str(dict_coord[oid][0]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['N', str(dict_coord[oid][1]).replace(',', '.'), f'OBJECTID = {oid}'],
                        ['azimute', '\'0° 0′ 0.00″\'', f'OBJECTID = {oid}']
                    ]
                )

# azimute('Lote_vertices')

