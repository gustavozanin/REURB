# -*- coding: utf-8 -*-

import os
import arcpy
from shutil import make_archive

from linearizar_arcos import linearizar_feicao
from tabulando_intersecao import tabulacao_intersecao
import caminho_camadas
from fusos_utm import (
    fusos_utm,
    bandas_utm_limites
)


def encontrar_fuso_utm(
    feicao_bairro: os.PathLike,
) -> tuple[str, str]:
    """
    Encontra o fuso UTM e a banda do bairro selecionado.
    """
    bairro_fuso = arcpy.MakeFeatureLayer_management(
        in_features=feicao_bairro,
        out_layer='bairro_fuso'
    )

    with arcpy.da.SearchCursor(bairro_fuso, ['SHAPE@']) as cursor:
        for row in cursor:
            area = row[0].getArea("GEODESIC", "SQUAREMETERS")
            centroide = row[0].centroid
            latitude = int(centroide.Y)

    banda_utm = None
    for banda, limites in bandas_utm_limites.items():
        if latitude >= limites[0] and latitude <= limites[1]:
            banda_utm = banda
            break

    intercecao_fuso = tabulacao_intersecao(
        feicao_perimetro=bairro_fuso,
        intersecao_dissolvida=caminho_camadas.fusos_utm_camada,
        class_fields=['CODE'],
        area=area
    )

    maior_porcentagem = 0
    codigo_fuso = None
    with arcpy.da.SearchCursor(intercecao_fuso, ['CODE', 'porcentagem']) as cursor:
        for row in cursor:
            if row[1] > maior_porcentagem:
                maior_porcentagem = row[1]
                codigo_fuso = row[0]

    return codigo_fuso, banda_utm


def exporta_shapefile(
    numero_reurb_coletivo: str,
    feicoes_bairro: os.PathLike
) -> tuple[os.PathLike, os.PathLike, str, str, float, float, float, str]:
    """
    Exporta o perímetro do bairro para shapefile e calcula área e perímetro.

    -------
    Returns:
        tuple:
            dir_shapefile, bairro_reprojetado, codigo_fuso, banda_utm,
            meridiano_central, area_bairro, perimetro_bairro, bairro
    """
    bairro_selecionado = arcpy.Select_analysis(
        in_features=feicoes_bairro,
        out_feature_class=os.path.join(arcpy.env.scratchGDB, 'bairro_selecionado'),
        where_clause=f"n_coletivo = '{numero_reurb_coletivo}'"
    )

    codigo_fuso_bairro, banda_utm = encontrar_fuso_utm(
        feicao_bairro=bairro_selecionado
    )

    bairro_reprojetado = arcpy.Project_management(
        in_dataset=bairro_selecionado,
        out_dataset='bairro_reprojetado',
        out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro])
    )

    # Não densifica a curva: área/perímetro do carimbo saem da geometria
    # original e os vértices do memorial/planta ficam os do projeto.

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
            row[0] = round(row[0], 2)
            row[1] = round(row[1], 2)
            cursor.updateRow(row)

    meridiano_central = arcpy.SpatialReference(
        fusos_utm[codigo_fuso_bairro]
    ).centralMeridian

    with arcpy.da.SearchCursor(bairro_reprojetado, ['area_m2', 'perimetro', 'nome']) as cursor:
        for row in cursor:
            area_bairro = row[0]
            perimetro_bairro = row[1]
            bairro = row[2]

    area_bairro = float(f'{area_bairro:.2f}')
    perimetro_bairro = float(f'{perimetro_bairro:.2f}')

    nome_base = f'loteamento_{numero_reurb_coletivo.replace("/", "_")}'
    dir_shapefile = os.path.join(arcpy.env.scratchFolder, nome_base)

    if not os.path.exists(dir_shapefile):
        os.mkdir(dir_shapefile)

    # Exporta o bairro já projetado no fuso do processo: o documento declara
    # UTM, então o shapefile precisa chegar ao registro no mesmo sistema.
    arcpy.CopyFeatures_management(
        in_features=bairro_reprojetado,
        out_feature_class=os.path.join(dir_shapefile, f'{nome_base}.shp')
    )

    return (
        dir_shapefile,
        bairro_reprojetado,
        codigo_fuso_bairro,
        banda_utm,
        meridiano_central,
        area_bairro,
        perimetro_bairro,
        bairro
    )


def zipar_shapefile(
    dir_shapefile: os.PathLike
) -> os.PathLike:
    """
    Zipa o shapefile exportado.
    """
    zip_lote = make_archive(
        base_name=dir_shapefile,
        format='zip',
        root_dir=dir_shapefile
    )
    return zip_lote
