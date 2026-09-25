# -*- coding: utf-8 -*-

import os
import arcpy


def check_responsavel_tecnico(
    feicao_bairro: os.PathLike,
    numero_reurb_coletivo: str,
    responsavel_tecnico_tabela: os.PathLike,
    formacao_override: str = None,
    credenciamento_override: str = None,
    nome_override: str = None,
) -> tuple:
    """
    Verifica se o responsável técnico existe no cadastro.

    nome_override: usa este nome se o campo no Bairro estiver vazio
      (comum no FeatureServer).
    formacao_override / credenciamento_override: pulam a consulta à tabela.
    """
    responsavel_tecnico = None
    formacao = None
    codigo_credenciamento = None

    with arcpy.da.SearchCursor(
        feicao_bairro,
        ['responsavel_tecnico'],
        where_clause=f"n_coletivo = '{numero_reurb_coletivo}'"
    ) as search_cursor:
        for row in search_cursor:
            responsavel_tecnico = row[0]

    if not responsavel_tecnico and nome_override:
        arcpy.AddMessage(
            f'Campo responsavel_tecnico vazio no Bairro; '
            f'usando nome informado na ferramenta: {nome_override}'
        )
        responsavel_tecnico = nome_override

    if not responsavel_tecnico:
        arcpy.AddError(
            'Responsável técnico não preenchido no bairro. '
            'Informe o nome do RT na ferramenta Desktop.'
        )
        return False, responsavel_tecnico, None, None

    if nome_override and formacao_override and credenciamento_override:
        arcpy.AddMessage(
            'Usando nome, formação e credenciamento informados na ferramenta'
        )
        return True, nome_override, formacao_override, credenciamento_override

    if (formacao_override or credenciamento_override) and not nome_override:
        arcpy.AddWarning(
            'Formação/CREA informados na ferramenta foram ignorados: '
            'o nome do responsável continua o do Bairro. Informe também o '
            'Nome do RT para usar outro cadastro, ou deixe formação e CREA '
            'em branco.'
        )

    with arcpy.da.SearchCursor(
        responsavel_tecnico_tabela,
        ['nome', 'formacao', 'credenciamento'],
        where_clause=f"nome = '{responsavel_tecnico}'"
    ) as search_cursor:
        for row in search_cursor:
            if row[0] == responsavel_tecnico:
                formacao = row[1]
                codigo_credenciamento = row[2]
                break

    if formacao is None or codigo_credenciamento is None:
        arcpy.AddError(
            f'Responsável técnico "{responsavel_tecnico}" não cadastrado '
            f'ou preenchimento incorreto na tabela de responsáveis. '
            f'Informe formação e CREA/CAU na ferramenta Desktop.'
        )
        return False, responsavel_tecnico, None, None

    return True, responsavel_tecnico, formacao, codigo_credenciamento
