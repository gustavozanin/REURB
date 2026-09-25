# -*- coding: utf-8 -*-

"""Tabela resumo de quadras sem ferramenta Advanced (Sort)."""

import os
import arcpy

from fusos_utm import fusos_utm


def __chave_quadra(valor):
    """Normaliza o número da quadra: 18, '18' e '018' viram a mesma chave."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        numero = float(texto.replace(',', '.'))
        if numero.is_integer():
            return str(int(numero))
        return str(numero)
    except ValueError:
        return texto.casefold()


def __chave_ordenacao(valor):
    """Chave sempre comparável: (tipo, numero, texto)."""
    if valor is None:
        return (2, 0.0, '')
    texto = str(valor).strip()
    try:
        return (0, float(texto.replace(',', '.')), '')
    except ValueError:
        return (1, 0.0, texto.lower())


def __ordenar_por_quadra(in_dataset: os.PathLike, out_name: str) -> str:
    """Copia feições ordenadas por campo quadra sem arcpy.Sort."""
    out_fc = os.path.join(arcpy.env.scratchGDB, out_name)
    if arcpy.Exists(out_fc):
        arcpy.Delete_management(out_fc)

    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(in_dataset)}
    if 'quadra' not in nomes:
        return arcpy.management.CopyFeatures(in_dataset, out_fc)

    campo_quadra = nomes['quadra']
    campos_full = ['SHAPE@'] + [
        f.name for f in arcpy.ListFields(in_dataset)
        if f.type not in ('OID', 'Geometry') and f.name.lower() != 'shape'
    ]

    dados = []
    with arcpy.da.SearchCursor(in_dataset, campos_full) as cursor:
        idx = campos_full.index(campo_quadra)
        for row in cursor:
            dados.append((__chave_ordenacao(row[idx]), row))
    dados.sort(key=lambda item: item[0])

    arcpy.management.CopyFeatures(in_dataset, out_fc)
    arcpy.management.DeleteRows(out_fc)

    with arcpy.da.InsertCursor(out_fc, campos_full) as icursor:
        for _, row in dados:
            icursor.insertRow(row)

    return out_fc


def __contar_lotes_por_quadra(quadra_layout: os.PathLike, lote_layout: os.PathLike) -> dict:
    """Conta lotes cujo centro está na quadra desenhada (não só o atributo)."""
    contagem = {}
    if int(arcpy.management.GetCount(lote_layout)[0]) == 0:
        return contagem

    nomes_q = {f.name.lower(): f.name for f in arcpy.ListFields(quadra_layout)}
    if 'quadra' not in nomes_q:
        return contagem

    saida = os.path.join(arcpy.env.scratchGDB, 'lote_com_quadra_espacial')
    if arcpy.Exists(saida):
        arcpy.Delete_management(saida)

    try:
        arcpy.analysis.SpatialJoin(
            target_features=lote_layout,
            join_features=quadra_layout,
            out_feature_class=saida,
            join_operation='JOIN_ONE_TO_ONE',
            join_type='KEEP_COMMON',
            match_option='HAVE_THEIR_CENTER_IN',
        )
        nomes = {f.name.lower(): f.name for f in arcpy.ListFields(saida)}
        campo = nomes.get('quadra_1') or nomes.get('quadra')
        if not campo:
            return contagem
        with arcpy.da.SearchCursor(saida, [campo]) as cursor:
            for row in cursor:
                chave = __chave_quadra(row[0])
                if chave is None:
                    continue
                contagem[chave] = contagem.get(chave, 0) + 1
        return contagem
    except Exception as exc:
        arcpy.AddWarning(
            f'Contagem espacial de lotes indisponível ({exc}); '
            f'usando o atributo quadra do lote.'
        )

    with arcpy.da.SearchCursor(lote_layout, ['quadra']) as cursor:
        for row in cursor:
            chave = __chave_quadra(row[0])
            if chave is None:
                continue
            contagem[chave] = contagem.get(chave, 0) + 1
    return contagem


def gerar_tabela_quadras(
    quadra_layout: os.PathLike,
    lote_layout: os.PathLike,
    codigo_fuso: str
) -> os.PathLike:
    """
    Gera tabela resumo de quadras com área total (m²) e quantitativo de lotes.
    """

    campos_manter = [campo.name for campo in arcpy.ListFields(quadra_layout) if campo.required]
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

    contagem_por_quadra = __contar_lotes_por_quadra(quadra_layout, lote_layout)

    registros = {}
    area_total_quadra = 0
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
                chave = __chave_quadra(quadra_num)
                qtd_lotes = contagem_por_quadra.get(chave, 0)
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

        quadra_ordenada = __ordenar_por_quadra(
            in_dataset=quadra_layout,
            out_name='quadra_layout_ordenada'
        )
        quadra_layout = arcpy.CopyFeatures_management(quadra_ordenada, quadra_layout)

    arcpy.AddMessage(
        f'Tabela de quadras gerada: {len(registros)} quadra(s) ordenadas por quadra crescente'
    )

    return quadra_layout, area_total_quadra, qtd_total_quadra
