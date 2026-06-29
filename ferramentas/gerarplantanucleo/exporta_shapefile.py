# -*- coding: utf-8 -*-

import os
import arcpy
import uuid
from shutil import make_archive

from tabulando_intersecao import tabulacao_intersecao, obter_workspace_temporario
from caminho_camadas import fusos_utm_camada
from fusos_utm import (
    fusos_utm,
    bandas_utm_limites
)
from normalizacao import arredondar_4

def encontrar_fuso_utm(
    feicao_bairro: os.PathLike,
) -> os.PathLike:
    """
    Responsável por encontrar o fuso utm do lote.

    -------
    Args:
        feicao_bairro(os.PathLike):
            Caminho para o bairro selecionado.

    -------
    Returns:
        os.PathLike:
            Caminho para o bairro selecionado.
    """
    bairro_fuso = arcpy.MakeFeatureLayer_management(
        in_features=feicao_bairro,
        out_layer=f'bairro_fuso_{uuid.uuid4().hex[:8]}'
    )

    with arcpy.da.SearchCursor(bairro_fuso, ['SHAPE@', 'SHAPE@TRUECENTROID']) as cursor:
        for row in cursor:
            area = row[0].getArea("GEODESIC", "SQUAREMETERS")
            centroide = row[0].centroid
            latitude = int(centroide.Y)
            longitude = int(centroide.X)

    for banda, limites in bandas_utm_limites.items():
        if latitude >= limites[0] and latitude <= limites[1]:
            banda_utm = banda
            break

    intercecao_fuso = tabulacao_intersecao(
        feicao_perimetro=bairro_fuso,
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
    numero_reurb_coletivo: str,
    feicoes_bairro: os.PathLike
) -> tuple[os.PathLike, os.PathLike, str, str, float, float, float]:
    """
    Responsável por exportar o lote para shapefile e zipar.

    -------
    Args:
        numero_reurb_coletivo(str):
            Número do REURB coletivo.
        feicoes_bairro(os.PathLike):
            Caminho para a camada das feições do bairro.

    -------
    Returns:
        tuple[os.PathLike, os.PathLike, str, str, float, float, float]:
            Tupla contendo o caminho para o shapefile do bairro zipado, a feature class do bairro selecionado, o código do fuso utm, a banda utm, o meridiano central, a área do bairro e o perímetro do bairro.
    """
    workspace_temp = obter_workspace_temporario()
    sufixo = uuid.uuid4().hex[:8]

    bairro_selecionado = arcpy.Select_analysis(
        in_features=feicoes_bairro,
        out_feature_class=os.path.join(workspace_temp, f'bairro_selecionado_{sufixo}'),
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\''
    )

    codigo_fuso_bairro, banda_utm = encontrar_fuso_utm(
        feicao_bairro=bairro_selecionado
    )

    #calcular área e perimetro do bairro
    bairro_reprojetado = arcpy.Project_management(
        in_dataset=bairro_selecionado,
        out_dataset=os.path.join(workspace_temp, f'bairro_reprojetado_{sufixo}'),
        out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro])
    )

    arcpy.AddFields_management(
        in_table=bairro_reprojetado,
        field_description=[
            ['area_m2', 'DOUBLE', 'area_m2'],
            ['perimetro', 'DOUBLE', 'perimetro']
        ]
    )

    arcpy.CalculateGeometryAttributes_management(
        in_features=bairro_reprojetado,
        geometry_property=[
            ['area_m2', 'AREA'],
            ['perimetro', 'PERIMETER_LENGTH']
        ],
        length_unit='METERS',
        area_unit='SQUARE_METERS',
        coordinate_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro])
    )

    with arcpy.da.UpdateCursor(bairro_reprojetado, ['area_m2', 'perimetro']) as cursor:
        for row in cursor:
            row[0] = arredondar_4(row[0])
            row[1] = arredondar_4(row[1])
            cursor.updateRow(row)

    meridiano_central = arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro]).centralMeridian

    with arcpy.da.SearchCursor(bairro_reprojetado, ['area_m2', 'perimetro']) as cursor:
        for row in cursor:
            area_bairro = row[0]
            perimetro_bairro = row[1]

    area_bairro = arredondar_4(area_bairro)
    perimetro_bairro = arredondar_4(perimetro_bairro)

    dir_shapefile = os.path.join(
        arcpy.env.scratchFolder,
        f'lote_{numero_reurb_coletivo.replace("/", "_")}'
    )
    if not os.path.exists(os.path.join(arcpy.env.scratchFolder, f'lote_{numero_reurb_coletivo.replace("/", "_")}')):
        os.mkdir(dir_shapefile)
    
    #exporta bairro selecionado para shapefile
    shp_saida = os.path.join(
        dir_shapefile,
        f'lote_{numero_reurb_coletivo.replace("/", "_")}.shp'
    )
    if arcpy.Exists(shp_saida):
        arcpy.Delete_management(shp_saida)

    arcpy.CopyFeatures_management(
        in_features=bairro_selecionado,
        out_feature_class=shp_saida
    )

    return dir_shapefile, bairro_reprojetado, codigo_fuso_bairro, banda_utm, meridiano_central, area_bairro, perimetro_bairro

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
