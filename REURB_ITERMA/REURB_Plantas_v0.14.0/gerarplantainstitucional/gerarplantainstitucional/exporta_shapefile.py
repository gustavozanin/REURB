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
        out_layer='bairro_fuso'
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
        intersecao_dissolvida=caminho_camadas.fusos_utm_camada,
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
    bairro_selecionado = arcpy.Select_analysis(
        in_features=feicoes_bairro,
        out_feature_class=os.path.join(arcpy.env.scratchGDB, 'bairro_selecionado'),
        where_clause=f'n_coletivo = \'{numero_reurb_coletivo}\''
    )
    quantidade = int(arcpy.management.GetCount(bairro_selecionado)[0])
    if quantidade != 1:
        raise ValueError(
            'O número do REURB deve identificar exatamente um perímetro; '
            f'foram encontradas {quantidade} feições para "{numero_reurb_coletivo}".'
        )

    codigo_fuso_bairro, banda_utm = encontrar_fuso_utm(
        feicao_bairro=bairro_selecionado
    )

    #calcular área e perimetro do bairro
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

    meridiano_central = arcpy.SpatialReference(fusos_utm[codigo_fuso_bairro]).centralMeridian

    with arcpy.da.SearchCursor(bairro_reprojetado, ['area_m2', 'perimetro', 'nome']) as cursor:
        for row in cursor:
            area_bairro = row[0]
            perimetro_bairro = row[1]
            bairro = row[2]

    area_bairro = float(f'{area_bairro:.2f}')
    perimetro_bairro = float(f'{perimetro_bairro:.2f}')

    dir_shapefile = os.path.join(
        arcpy.env.scratchFolder,
        f'bairro_{numero_reurb_coletivo.replace("/", "_")}'
    )
    if not os.path.exists(os.path.join(arcpy.env.scratchFolder, f'bairro_{numero_reurb_coletivo.replace("/", "_")}')):
        os.mkdir(dir_shapefile)
    
    # Exporta o bairro já projetado no fuso do processo: o documento declara
    # UTM, então o shapefile precisa chegar ao registro no mesmo sistema.
    arcpy.CopyFeatures_management(
        in_features=bairro_reprojetado,
        out_feature_class=os.path.join(
            dir_shapefile,
            f'bairro_{numero_reurb_coletivo.replace("/", "_")}.shp'
        )
    )

    return dir_shapefile, bairro_reprojetado, codigo_fuso_bairro, banda_utm, meridiano_central, area_bairro, perimetro_bairro, bairro


def exporta_lote_institucional(
    numero_reurb_coletivo: str,
    feicoes_lote: os.PathLike,
    quadra,
    lote: str,
    where_clause: str = None,
) -> tuple:
    """Exporta um lote (polígono) para UTM, lineariza arcos e mede área/perímetro.

    Espelha `exporta_shapefile` do bairro, com where de lote
    (n_coletivo + quadra + lote).
    """
    from check_lote_institucional import montar_where_lote

    where = where_clause or montar_where_lote(
        numero_reurb_coletivo, quadra, lote
    )
    lote_selecionado = arcpy.Select_analysis(
        in_features=feicoes_lote,
        out_feature_class=os.path.join(arcpy.env.scratchGDB, 'lote_selecionado'),
        where_clause=where,
    )
    quantidade = int(arcpy.management.GetCount(lote_selecionado)[0])
    if quantidade != 1:
        raise ValueError(
            'A chave REURB+quadra+lote deve identificar exatamente um lote; '
            f'foram encontradas {quantidade} feições.'
        )

    codigo_fuso, banda_utm = encontrar_fuso_utm(feicao_bairro=lote_selecionado)

    lote_reprojetado = arcpy.Project_management(
        in_dataset=lote_selecionado,
        out_dataset='lote_reprojetado',
        out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso]),
    )
    # Vértices do memorial = vértices do projeto (sem densificar o arco).

    arcpy.AddFields_management(
        in_table=lote_reprojetado,
        field_description=[
            ['area_m2', 'DOUBLE', 'area_m2'],
            ['perimetro', 'DOUBLE', 'perimetro'],
        ],
    )
    arcpy.CalculateGeometryAttributes_management(
        in_features=lote_reprojetado,
        geometry_property=[
            ['area_m2', 'AREA'],
            ['perimetro', 'PERIMETER_LENGTH'],
        ],
        length_unit='METERS',
        area_unit='SQUARE_METERS',
        coordinate_system=arcpy.SpatialReference(fusos_utm[codigo_fuso]),
    )
    with arcpy.da.UpdateCursor(lote_reprojetado, ['area_m2', 'perimetro']) as cursor:
        for row in cursor:
            row[0] = round(row[0], 2)
            row[1] = round(row[1], 2)
            cursor.updateRow(row)

    meridiano_central = arcpy.SpatialReference(
        fusos_utm[codigo_fuso]
    ).centralMeridian

    # Campos opcionais para meta (bairro do atributo do lote)
    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(lote_reprojetado)}
    campos_leitura = ['area_m2', 'perimetro']
    for candidato in ('bairro', 'nome'):
        if candidato in nomes:
            campos_leitura.append(nomes[candidato])

    area_lote = perimetro_lote = None
    bairro_attr = None
    nome_attr = None
    with arcpy.da.SearchCursor(lote_reprojetado, campos_leitura) as cursor:
        for row in cursor:
            area_lote = float(f'{row[0]:.2f}')
            perimetro_lote = float(f'{row[1]:.2f}')
            idx = 2
            if 'bairro' in nomes:
                bairro_attr = row[idx]
                idx += 1
            if 'nome' in nomes:
                nome_attr = row[idx]
            break

    slug = (
        f'{numero_reurb_coletivo.replace("/", "_")}'
        f'_Q{quadra}_L{lote}'
    )
    dir_shapefile = os.path.join(arcpy.env.scratchFolder, f'lote_{slug}')
    if not os.path.exists(dir_shapefile):
        os.mkdir(dir_shapefile)

    arcpy.CopyFeatures_management(
        in_features=lote_reprojetado,
        out_feature_class=os.path.join(dir_shapefile, f'lote_{slug}.shp'),
    )

    return (
        dir_shapefile,
        lote_reprojetado,
        codigo_fuso,
        banda_utm,
        meridiano_central,
        area_lote,
        perimetro_lote,
        bairro_attr,
        nome_attr,
    )


def exportar_camadas_do_perimetro(
    dir_shapefile: os.PathLike,
    numero_reurb_coletivo: str,
    vertices: os.PathLike,
    segmentos: os.PathLike
) -> None:
    """
    Acrescenta ao ZIP os vértices e os segmentos descritos no documento.

    Quem confere no registro precisa reencontrar no shapefile os mesmos
    P-xxx, azimutes, distâncias e confrontantes que leu no quadro; só o
    polígono do bairro não permite essa conferência.

    -------
    Args:
        dir_shapefile(os.PathLike):
            Pasta do shapefile que será zipada.
        numero_reurb_coletivo(str):
            Número do REURB coletivo, usado no nome dos arquivos.
        vertices(os.PathLike):
            Feição de pontos dos vértices (saída do motor de perímetro).
        segmentos(os.PathLike):
            Feição de linhas dos segmentos, já com confrontantes.
    """
    slug = numero_reurb_coletivo.replace('/', '_')
    for feicao, nome in ((vertices, 'vertices'), (segmentos, 'segmentos')):
        if feicao is None:
            continue
        arcpy.CopyFeatures_management(
            in_features=feicao,
            out_feature_class=os.path.join(dir_shapefile, f'{nome}_{slug}.shp')
        )
    arcpy.AddMessage('Vértices e segmentos adicionados ao shapefile do ZIP')

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
