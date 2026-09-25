# -*- coding: utf-8 -*-
"""Garante que os módulos locais desta pasta sejam usados (evita conflito com Núcleo/Loteamento).

A ativação do `sys.path` é feita em `GerarPlantaInstitucional.pyt`
(`_ativar_pasta_desta_toolbox`). Este módulo mantém a lista de nomes
compartilhados para referência e reload.
"""

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
    'memorial_narrativo',
    'gerar_planta_perimetro',
    'gerar_planta_institucional',
    'exportar_pdf_unificado',
    'pipeline_perimetro',
    'linearizar_arcos',
    'constantes',
    'dominio_status_lote',
    'check_lote_institucional',
    'documentos_pdf',
    'autenticacao_documentos',
    'motor_perimetro',
    'simplificar_vertices',
    'azimute_utm',
)
