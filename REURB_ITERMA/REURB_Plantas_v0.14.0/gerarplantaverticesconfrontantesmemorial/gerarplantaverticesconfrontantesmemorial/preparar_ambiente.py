# -*- coding: utf-8 -*-
"""Garante que os módulos locais desta pasta sejam usados (evita conflito com Núcleo/Loteamento)."""

import os
import sys

# Módulos com o mesmo nome em outras ferramentas do pacote (Núcleo/Loteamento)
_MODULOS_COMPARTILHADOS = (
    'caminho_camadas',
    'fluxo_geracao',
    'exporta_shapefile',
    'salvar_artefatos_desktop',
    'check_responsavel',
    'check_reurb_coletivo',
    'check_status',
    'municipalidade',
    'tabela_modelo',
    'caminho_simbologias',
    'caminhos_gerais',
    'fusos_utm',
    'tabulando_intersecao',
    'confrontantes',
    'transforma_feicao',
    'transforma_vertices_em_linhas',
    'formatar_tabela_atributos',
    'formatar_dados_perimetro',
    'variaveis_globais',
    'logger',
)


def preparar_ambiente_local(pasta_ferramenta=None):
    """
    Coloca a pasta da ferramenta no início do sys.path e remove
    módulos já importados de outra ferramenta do pacote.
    """
    if pasta_ferramenta is None:
        pasta_ferramenta = os.path.dirname(os.path.abspath(__file__))

    # Remove entradas das três toolboxes e reinsere a local na frente
    limpos = []
    for p in sys.path:
        pl = p.replace('\\', '/').lower()
        if (
            'gerarplantanucleo' in pl
            or 'gerarplantaloteamento' in pl
            or 'gerarplantaverticesconfrontantesmemorial' in pl
        ):
            continue
        limpos.append(p)
    sys.path[:] = limpos
    sys.path.insert(0, pasta_ferramenta)

    for nome in _MODULOS_COMPARTILHADOS:
        sys.modules.pop(nome, None)

    return pasta_ferramenta
