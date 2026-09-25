# -*- coding: utf-8 -*-
"""Regras de seleção do lote institucional (lógica pura + resolução ArcPy).

A seleção usa where n_coletivo + quadra + lote.
Regras puras: cardinalidade, status, validado ignorado, aviso Situação/Observação.
"""

from __future__ import annotations

import arcpy

from dominio_status_lote import eh_institucional, rotulo_do_valor


class LoteInstitucionalErro(ValueError):
    """Erro de negócio na resolução do lote institucional."""


def avaliar_cardinalidade(n_feicoes: int) -> None:
    if n_feicoes <= 0:
        raise LoteInstitucionalErro('Lote não existe na quadra para o REURB informado.')
    if n_feicoes > 1:
        raise LoteInstitucionalErro(
            f'Ambiguidade: {n_feicoes} feições com a mesma chave '
            'n_coletivo + quadra + lote.'
        )


def avaliar_status_institucional(valor_status, mapa_dominio: dict | None = None) -> str:
    """Garante status institucional; retorna rótulo para log/carimbo."""
    if not eh_institucional(valor_status, mapa_dominio):
        rotulo = rotulo_do_valor(valor_status, mapa_dominio) or str(valor_status)
        raise LoteInstitucionalErro(
            f'Lote não é institucional (status={rotulo}). '
            'Aceitos: Institucional Municipal ou Institucional Estadual.'
        )
    return rotulo_do_valor(valor_status, mapa_dominio)


def validado_bloqueia(valor_validado) -> bool:
    """Sempre False: validado nulo/Pendente/Validado não bloqueia (AD-015)."""
    return False


def textos_aviso_cadastro(situacao=None, observacao=None) -> list[str]:
    """Monta avisos para AddWarning; vazio se ambos nulos/em branco."""
    avisos = []
    sit = '' if situacao is None else str(situacao).strip()
    obs = '' if observacao is None else str(observacao).strip()
    for rotulo, valor in (('Situação', sit), ('Observação', obs)):
        if not valor or valor.lower() in ('<nulo>', 'none', 'null'):
            continue
        avisos.append(f'{rotulo} do lote: {valor}')
    return avisos


def limpar_texto_carimbo(valor) -> str:
    """Remove espaços e hífens soltos no fim (comum em Nome do cadastro)."""
    if valor is None:
        return ''
    texto = str(valor).strip()
    if texto.lower() in ('<nulo>', 'none', 'null'):
        return ''
    return texto.rstrip(' -—–\t')


def montar_titulo_imovel(nome, quadra, lote) -> str:
    """Título do carimbo: Nome ou fallback Institucional — Qx/Ly."""
    nome_limpo = limpar_texto_carimbo(nome)
    if nome_limpo:
        return nome_limpo
    return f'Institucional — Q{quadra}/L{lote}'


def montar_where_lote(numero_reurb_coletivo: str, quadra, lote: str) -> str:
    """Where clause alinhada ao gerarplantareurb."""
    reurb = str(numero_reurb_coletivo).strip().replace("'", "''")
    lote_txt = str(lote).strip().replace("'", "''")
    quadra_txt = str(quadra).strip()
    try:
        quadra_sql = str(int(quadra_txt))
    except ValueError:
        quadra_sql = f"'{quadra_txt.replace(chr(39), chr(39) * 2)}'"
    return (
        f"n_coletivo = '{reurb}' AND quadra = {quadra_sql} "
        f"AND lote = '{lote_txt}'"
    )


def _campo_por_nome(camada, *candidatos: str):
    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(camada)}
    for c in candidatos:
        if c.lower() in nomes:
            return nomes[c.lower()]
    return None


def mapa_dominio_campo(dataset, field_name: str) -> dict:
    """Código → descrição do domínio do campo (FeatureServer pode falhar → {})."""
    campo = next(
        (
            f
            for f in arcpy.ListFields(dataset)
            if f.name.lower() == field_name.lower()
        ),
        None,
    )
    if campo is None or not getattr(campo, 'domain', None):
        return {}
    try:
        catalog = arcpy.Describe(dataset).catalogPath
        lower = catalog.lower()
        workspace = arcpy.Describe(dataset).path
        for ext in ('.sde', '.gdb'):
            idx = lower.find(ext)
            if idx != -1:
                workspace = catalog[: idx + len(ext)]
                break
        domains = arcpy.da.ListDomains(workspace)
    except Exception:
        return {}
    for domain in domains:
        if domain.name != campo.domain:
            continue
        if getattr(domain, 'domainType', None) == 'CodedValue':
            return dict(domain.codedValues.items())
    return {}


def resolver_lote_institucional(
    lote_camada,
    numero_reurb_coletivo: str,
    quadra,
    lote: str,
    mapa_dominio: dict | None = None,
) -> dict:
    """Localiza exatamente 1 lote institucional e devolve atributos úteis.

    Raises:
        LoteInstitucionalErro: 0/>1 feições ou status não institucional.
    """
    where = montar_where_lote(numero_reurb_coletivo, quadra, lote)
    mapa = mapa_dominio
    if mapa is None:
        mapa = mapa_dominio_campo(lote_camada, 'status')

    campo_status = _campo_por_nome(lote_camada, 'status')
    campo_nome = _campo_por_nome(lote_camada, 'nome')
    campo_rua = _campo_por_nome(lote_camada, 'rua')
    campo_sit = _campo_por_nome(lote_camada, 'situacao')
    campo_obs = _campo_por_nome(lote_camada, 'observacao', 'obs')
    campo_val = _campo_por_nome(lote_camada, 'validado')
    campo_quadra = _campo_por_nome(lote_camada, 'quadra')
    campo_lote = _campo_por_nome(lote_camada, 'lote')

    if not campo_status:
        raise LoteInstitucionalErro('Campo status não encontrado na camada Lotes.')

    campos = [campo_status]
    for c in (
        campo_nome,
        campo_rua,
        campo_sit,
        campo_obs,
        campo_val,
        campo_quadra,
        campo_lote,
    ):
        if c and c not in campos:
            campos.append(c)

    rows = []
    with arcpy.da.SearchCursor(lote_camada, campos, where_clause=where) as cursor:
        for row in cursor:
            rows.append(row)

    avaliar_cardinalidade(len(rows))
    row = rows[0]
    dados = dict(zip(campos, row))

    status_val = dados[campo_status]
    _ = validado_bloqueia(dados.get(campo_val) if campo_val else None)

    status_rotulo = avaliar_status_institucional(status_val, mapa)
    nome = dados.get(campo_nome) if campo_nome else None
    rua = limpar_texto_carimbo(dados.get(campo_rua) if campo_rua else None)
    situacao = dados.get(campo_sit) if campo_sit else None
    observacao = dados.get(campo_obs) if campo_obs else None
    q = dados.get(campo_quadra) if campo_quadra else quadra
    l = dados.get(campo_lote) if campo_lote else lote
    avisos = textos_aviso_cadastro(situacao, observacao)
    if not rua:
        avisos.append(
            'Campo Rua vazio no lote; Logradouro do carimbo ficará em branco.'
        )

    return {
        'where': where,
        'n_coletivo': numero_reurb_coletivo,
        'quadra': q,
        'lote': l,
        'nome': nome,
        'rua': rua,
        'status': status_val,
        'status_rotulo': status_rotulo,
        'situacao': situacao,
        'observacao': observacao,
        'titulo': montar_titulo_imovel(nome, q, l),
        'avisos': avisos,
    }
