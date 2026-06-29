# -*- coding: utf-8 -*-

import os
import arcpy
from shutil import make_archive

from tabulando_intersecao import tabulacao_intersecao
from caminho_camadas import fusos_utm_camada
from fusos_utm import (
    fusos_utm,
    bandas_utm_limites
)

def encontrar_fuso_utm(
    lote_feature: os.PathLike,
) -> os.PathLike:
    """
    Responsável por encontrar o fuso utm do lote.

    -------
    Args:
        lote_feature(os.PathLike):
            Caminho para o shapefile do lote.

    -------
    Returns:
        os.PathLike:
            Caminho para o shapefile do lote.
    """
    lote_fuso = arcpy.MakeFeatureLayer_management(
        in_features=lote_feature,
        out_layer='lote_fuso'
    )

    # arcpy.AddField_management(
    #     in_table=lote_fuso,
    #     field_name='area_m2',
    #     field_type='DOUBLE'
    # )

    # arcpy.CalculateGeometryAttributes_management(
    #     in_features=lote_fuso,
    #     geometry_property=[
    #         ['area_m2', 'AREA_GEODESIC']
    #     ],
    #     area_unit='SQUARE_METERS',
    #     coordinate_system=arcpy.SpatialReference(4674)
    # )

    with arcpy.da.SearchCursor(lote_fuso, ['SHAPE@', 'SHAPE@TRUECENTROID']) as cursor:
        for row in cursor:
            area = row[0].getArea("GEODESIC", "SQUAREMETERS")
            centroide = row[0].centroid
            latitude = int(centroide.Y)
            longitude = int(centroide.X)
            # area = row[0]
            arcpy.AddMessage(area)

    print(area)

    for banda, limites in bandas_utm_limites.items():
        if latitude >= limites[0] and latitude <= limites[1]:
            banda_utm = banda
            print(banda_utm)
            break

    intercecao_fuso = tabulacao_intersecao(
        feicao_propriedade=lote_fuso,
        intersecao_dissolvida=fusos_utm_camada,
        class_fields=[
            'CODE'
        ],
        area=area
    )

    with arcpy.da.SearchCursor(intercecao_fuso, ['CODE', 'porcentagem']) as cursor:
        #pegar a maior porcentagem
        maior_porcentagem = 0
        for row in cursor:
            if row[1] > maior_porcentagem:
                maior_porcentagem = row[1]
                codigo_fuso = row[0]
    
    return codigo_fuso, banda_utm

def exporta_shapefile(
    lote_features: os.PathLike,
    numero_reurb_coletivo: int,
    quadra: int,
    lote: str
) -> tuple[os.PathLike, os.PathLike, str]:
    """
    Responsável por exportar o lote para shapefile e zipar.

    -------
    Args:
        lote_features(os.PathLike):
            Caminho para o shapefile do lote.
        numero_reurb_coletivo(int):
            Número do REURB coletivo.
        quadra(int):
            Número da quadra do lote.
        lote(str):
            Número do lote.

    -------
    Returns:
        tuple[os.PathLike, os.PathLike, str]:
            Tupla contendo o caminho para o shapefile do lote zipado, a feature class do lote selecionado e o código do fuso utm.
    """
    lote_selecionado = arcpy.Select_analysis(
        in_features=lote_features,
        out_feature_class=os.path.join(arcpy.env.scratchGDB, 'lote_selecionado'),
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\' AND quadra = {quadra} AND lote = \'{lote}\''
    )

    codigo_fuso_lote, banda_utm = encontrar_fuso_utm(
        lote_feature=lote_selecionado
    )

    #calcular área e perimetro do lote
    lote_reprojetado = arcpy.Project_management(
        in_dataset=lote_selecionado,
        out_dataset='lote_reprojetado',
        out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_lote])
    )

    arcpy.AddFields_management(
        in_table=lote_reprojetado,
        field_description=[
            ['area_m2', 'DOUBLE', 'area_m2'],
            ['perimetro', 'DOUBLE', 'perimetro']
        ]
    )

    arcpy.CalculateGeometryAttributes_management(
        in_features=lote_reprojetado,
        geometry_property=[
            ['area_m2', 'AREA'],
            ['perimetro', 'PERIMETER_LENGTH']
        ],
        length_unit='METERS',
        area_unit='SQUARE_METERS',
        coordinate_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_lote])
    )

    with arcpy.da.UpdateCursor(lote_reprojetado, ['area_m2', 'perimetro']) as cursor:
        for row in cursor:
            row[0] = round(row[0], 2)
            row[1] = round(row[1], 2)
            cursor.updateRow(row)

    meridiano_central = arcpy.SpatialReference(fusos_utm[codigo_fuso_lote]).centralMeridian

    with arcpy.da.SearchCursor(lote_reprojetado, ['area_m2', 'perimetro', 'n_predial', 'rua', 'bairro']) as cursor:
        for row in cursor:
            area_lote = row[0]
            perimetro_lote = row[1]
            n_predial = row[2]
            rua = row[3]
            bairro = row[4]

    area_lote = float(f'{area_lote:.2f}')
    perimetro_lote = float(f'{perimetro_lote:.2f}')

    dir_shapefile = os.path.join(
        arcpy.env.scratchFolder,
        f'lote_{numero_reurb_coletivo.replace("/", "_")}_{quadra}_{lote}'
    )
    if not os.path.exists(os.path.join(arcpy.env.scratchFolder, f'lote_{numero_reurb_coletivo.replace("/", "_")}_{quadra}_{lote}')):
        os.mkdir(dir_shapefile)
    
    #exporta lote selecionado para shapefile
    arcpy.CopyFeatures_management(
        in_features=lote_selecionado,
        out_feature_class=os.path.join(
            dir_shapefile,
            f'lote_{numero_reurb_coletivo.replace("/", "_")}_{quadra}_{lote}.shp'
        )
    )

    return dir_shapefile, lote_reprojetado, codigo_fuso_lote, banda_utm, meridiano_central, area_lote, perimetro_lote, n_predial, rua, bairro

def zipar_shapefile(
    dir_shapefile: os.PathLike
) -> os.PathLike:
    """
    Responsável por zipar o shapefile.

    -------
    Args:
        dir_shapefile: os.PathLike
            Caminho para o diretório do shapefile.

    -------
    Returns:
        os.PathLike:
            Caminho para o zip do shapefile.
    """
    zip_lote = make_archive(
        base_name=dir_shapefile,
        format='zip',
        root_dir=dir_shapefile
    )
    return zip_lote