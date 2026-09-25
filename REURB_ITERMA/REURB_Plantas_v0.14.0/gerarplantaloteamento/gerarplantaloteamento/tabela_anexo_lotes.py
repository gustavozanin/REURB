# -*- coding: utf-8 -*-

"""Prepara tabela anexo de lotes sem ferramentas Advanced (Sort)."""

import os
import arcpy


CAMPOS_ANEXO = (
    'quadra',
    'lote',
    'nome',
    'cpf_cnpj',
    'status',
    'situacao',
)


def __obter_workspace(dataset: os.PathLike) -> str:
    """Retorna o workspace (GDB ou SDE) da feição."""
    catalog_path = arcpy.Describe(dataset).catalogPath
    lower = catalog_path.lower()
    for ext in ('.sde', '.gdb'):
        indice = lower.find(ext)
        if indice != -1:
            return catalog_path[:indice + len(ext)]
    return arcpy.Describe(dataset).path


def __mapa_dominio(dataset: os.PathLike, field_name: str) -> dict:
    """Monta dicionário código -> descrição do domínio do campo."""
    campo = next(
        (
            field
            for field in arcpy.ListFields(dataset)
            if field.name.lower() == field_name.lower()
        ),
        None
    )
    if campo is None or not getattr(campo, 'domain', None):
        return {}

    try:
        domains = arcpy.da.ListDomains(__obter_workspace(dataset))
    except Exception:
        return {}

    for domain in domains:
        if domain.name != campo.domain:
            continue
        if getattr(domain, 'domainType', None) == 'CodedValue':
            return {
                codigo: descricao
                for codigo, descricao in domain.codedValues.items()
            }
    return {}


def __rotulo_dominio(valor, mapa: dict) -> str:
    """Converte valor de domínio para texto legível."""
    if valor is None:
        return ''
    if valor in mapa:
        return str(mapa[valor])
    if str(valor) in mapa:
        return str(mapa[str(valor)])
    try:
        if int(valor) in mapa:
            return str(mapa[int(valor)])
    except (TypeError, ValueError):
        pass
    return str(valor)


def __chave_ordenacao(valor):
    """Chave sempre comparável: (tipo, numero, texto)."""
    if valor is None:
        return (2, 0.0, '')
    texto = str(valor).strip()
    try:
        return (0, float(texto.replace(',', '.')), '')
    except ValueError:
        return (1, 0.0, texto.lower())


def __ordenar_por_campos(
    in_dataset: os.PathLike,
    out_name: str,
    campos_sort: list
) -> str:
    """Copia feições ordenadas sem arcpy.Sort (licença Advanced)."""
    out_fc = os.path.join(arcpy.env.scratchGDB, out_name)
    if arcpy.Exists(out_fc):
        arcpy.Delete_management(out_fc)

    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(in_dataset)}
    for campo in campos_sort:
        if campo.lower() not in nomes:
            raise ValueError(f'Campo de ordenação não encontrado: {campo}')

    campos_full = ['SHAPE@'] + [
        f.name for f in arcpy.ListFields(in_dataset)
        if f.type not in ('OID', 'Geometry') and f.name.lower() != 'shape'
    ]
    indices_sort = [campos_full.index(nomes[c.lower()]) for c in campos_sort]

    dados = []
    with arcpy.da.SearchCursor(in_dataset, campos_full) as cursor:
        for row in cursor:
            chaves = tuple(__chave_ordenacao(row[i]) for i in indices_sort)
            dados.append((chaves, row))
    dados.sort(key=lambda item: item[0])

    arcpy.management.CopyFeatures(in_dataset, out_fc)
    arcpy.management.DeleteRows(out_fc)

    with arcpy.da.InsertCursor(out_fc, campos_full) as icursor:
        for _, row in dados:
            icursor.insertRow(row)

    return out_fc


def gerar_tabela_anexo_lotes(
    lote_layout: os.PathLike,
    feicao_dominio: os.PathLike = None
) -> os.PathLike:
    """
    Prepara a feição de lotes para a tabela anexo:
    ordena por quadra/lote e resolve rótulos de status e situação.
    """
    origem_dominio = feicao_dominio or lote_layout

    if int(arcpy.management.GetCount(lote_layout)[0]) == 0:
        lote_anexo = arcpy.management.CopyFeatures(
            in_features=lote_layout,
            out_feature_class='lote_anexo'
        )
        arcpy.AddMessage('Tabela anexo de lotes: nenhum lote encontrado')
        return lote_anexo

    mapa_status = __mapa_dominio(origem_dominio, 'status')
    mapa_situacao = __mapa_dominio(origem_dominio, 'situacao')
    if not mapa_status:
        mapa_status = __mapa_dominio(lote_layout, 'status')
    if not mapa_situacao:
        mapa_situacao = __mapa_dominio(lote_layout, 'situacao')

    lote_ordenado = __ordenar_por_campos(
        in_dataset=lote_layout,
        out_name='lote_anexo_ordenado',
        campos_sort=['quadra', 'lote']
    )

    campos_existentes = {
        field.name.lower(): field.name
        for field in arcpy.ListFields(lote_ordenado)
    }
    campos_manter = [
        field.name
        for field in arcpy.ListFields(lote_ordenado)
        if field.required
    ]
    for campo in CAMPOS_ANEXO:
        if campo.lower() in campos_existentes:
            campos_manter.append(campos_existentes[campo.lower()])

    arcpy.management.DeleteField(
        in_table=lote_ordenado,
        drop_field=campos_manter,
        method='KEEP_FIELDS'
    )

    nomes_apos_delete = [f.name.lower() for f in arcpy.ListFields(lote_ordenado)]
    if 'status_txt' not in nomes_apos_delete:
        arcpy.management.AddField(
            in_table=lote_ordenado,
            field_name='status_txt',
            field_type='TEXT',
            field_length=100,
            field_alias='Status de andamento'
        )
    if 'situacao_txt' not in nomes_apos_delete:
        arcpy.management.AddField(
            in_table=lote_ordenado,
            field_name='situacao_txt',
            field_type='TEXT',
            field_length=100,
            field_alias='Situação'
        )

    nomes_campos = {f.name.lower(): f.name for f in arcpy.ListFields(lote_ordenado)}
    campo_status = nomes_campos.get('status')
    campo_situacao = nomes_campos.get('situacao')

    campos_cursor = ['status_txt', 'situacao_txt']
    indice_status = None
    indice_situacao = None
    if campo_status:
        indice_status = len(campos_cursor)
        campos_cursor.append(campo_status)
    if campo_situacao:
        indice_situacao = len(campos_cursor)
        campos_cursor.append(campo_situacao)

    with arcpy.da.UpdateCursor(lote_ordenado, campos_cursor) as cursor:
        for row in cursor:
            status_val = row[indice_status] if indice_status is not None else None
            situacao_val = row[indice_situacao] if indice_situacao is not None else None
            row[0] = __rotulo_dominio(status_val, mapa_status)
            row[1] = __rotulo_dominio(situacao_val, mapa_situacao)
            cursor.updateRow(row)

    lote_anexo = arcpy.management.CopyFeatures(
        in_features=lote_ordenado,
        out_feature_class='lote_anexo'
    )

    n_lotes = int(arcpy.management.GetCount(lote_anexo)[0])
    arcpy.AddMessage(
        f'Tabela anexo de lotes gerada: {n_lotes} lote(s) ordenados por quadra/lote'
    )
    return lote_anexo
