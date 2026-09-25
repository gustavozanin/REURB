# -*- coding: utf-8 -*-

import os
import arcpy

from fusos_utm import fusos_utm


def gerar_tabela_quadras(
    quadra_layout: os.PathLike,
    lote_layout: os.PathLike,
    codigo_fuso: str
) -> tuple[os.PathLike, float, int]:
    """
    Gera tabela resumo de quadras com área total (m²) e quantitativo de lotes.
    """
    campos_manter = [
        campo.name for campo in arcpy.ListFields(quadra_layout) if campo.required
    ]
    campos_manter.append('quadra')

    arcpy.DeleteField_management(
        in_table=quadra_layout,
        drop_field=campos_manter,
        method='KEEP_FIELDS'
    )

    arcpy.AddField_management(
        in_table=quadra_layout,
        field_name='area_m2',
        field_type='DOUBLE',
        field_alias='Área (m²)'
    )
    arcpy.AddField_management(
        in_table=quadra_layout,
        field_name='qtd_lotes',
        field_type='LONG',
        field_alias='Qtd. de Lotes'
    )

    contagem_por_quadra = {}
    if int(arcpy.management.GetCount(lote_layout)[0]) > 0:
        with arcpy.da.SearchCursor(lote_layout, ['quadra']) as cursor:
            for row in cursor:
                quadra_num = row[0]
                contagem_por_quadra[quadra_num] = contagem_por_quadra.get(quadra_num, 0) + 1

    registros = {}
    area_total_quadra = 0.0
    qtd_total_quadra = 0

    if int(arcpy.management.GetCount(quadra_layout)[0]) > 0:
        quadra_com_area = arcpy.Project_management(
            in_dataset=quadra_layout,
            out_dataset='quadra_com_area',
            out_coor_system=arcpy.SpatialReference(fusos_utm[codigo_fuso])
        )

        arcpy.CalculateGeometryAttributes_management(
            in_features=quadra_com_area,
            geometry_property=[['area_m2', 'AREA']],
            length_unit='METERS',
            area_unit='SQUARE_METERS',
            coordinate_system=arcpy.SpatialReference(fusos_utm[codigo_fuso])
        )

        with arcpy.da.SearchCursor(quadra_com_area, ['quadra', 'area_m2']) as cursor:
            for row in cursor:
                quadra_num = row[0]
                area = round(row[1], 2)
                qtd_lotes = contagem_por_quadra.get(quadra_num, 0)
                registros[quadra_num] = {
                    'area_m2': area,
                    'qtd_lotes': qtd_lotes
                }
                area_total_quadra += area
                qtd_total_quadra += qtd_lotes

        area_total_quadra = round(area_total_quadra, 2)
        qtd_total_quadra = int(qtd_total_quadra)

        with arcpy.da.UpdateCursor(quadra_layout, ['quadra', 'area_m2', 'qtd_lotes']) as cursor:
            for row in cursor:
                quadra_num = row[0]
                row[1] = registros[quadra_num]['area_m2']
                row[2] = registros[quadra_num]['qtd_lotes']
                cursor.updateRow(row)

        quadra_ordenada = arcpy.management.Sort(
            in_dataset=quadra_layout,
            out_dataset='quadra_layout_ordenada',
            sort_field='quadra ASCENDING'
        )
        quadra_layout = arcpy.CopyFeatures_management(quadra_ordenada, quadra_layout)

    arcpy.AddMessage(
        f'Tabela de quadras gerada: {len(registros)} quadra(s) ordenadas por quadra crescente'
    )

    return quadra_layout, area_total_quadra, qtd_total_quadra