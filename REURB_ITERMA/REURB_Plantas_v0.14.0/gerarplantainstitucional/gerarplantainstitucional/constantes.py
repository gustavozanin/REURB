# -*- coding: utf-8 -*-
"""Constantes compartilhadas (sem dependência de ArcPy)."""

# Texto padronizado quando o segmento não tem confrontante levantado.
CONFRONTANTE_PADRAO = 'LOTE DE TERCEIROS - NÃO IDENTIFICADO'

# Trecho curto entre vizinhos iguais: provável cruzamento transversal de eixo.
COMPRIMENTO_MAX_ABSORCAO_CONFRONTANTE_M = 15.0

# Confrontação de lote: aresta compartilhada (evita canto falso tipo L02 na avenida).
BUFFER_ARESTA_CONFRONTANTE_M = 0.5
OVERLAP_MINIMO_CONFRONTANTE_M = 5.0
OVERLAP_MINIMO_FRACAO_SEGMENTO = 0.40
# Layer Confrontante Externo: buffer maior que o de lote vizinho.
BUFFER_CONFRONTANTE_EXTERNO_M = 5.0

# Eixo viário à frente da testada (lote institucional).
BUFFER_BUSCA_EIXO_M = 40.0
PARALELISMO_MINIMO_EIXO = 0.707
PARALELISMO_MINIMO_EIXO_FALLBACK = 0.5
PARALELISMO_MINIMO_EIXO_ULTIMO = 0.3
DISTANCIA_MAX_EIXO_M = 40.0
DISTANCIA_MAX_EIXO_QUEBRA_M = 10.0
COMPRIMENTO_MAX_QUEBRA_ABRUPTA_M = 5.0
COSSENO_MAX_QUEBRA_ABRUPTA = 0.3

# Rótulos de confrontante na planta institucional de lote (escala menor).
COMPRIMENTO_MINIMO_ROTULO_LINHA_LOTE_M = 10.0
COMPRIMENTO_MAX_ROTULO_PONTO_LOTE_M = 10.0
DISTANCIA_MINIMA_ROTULOS_LOTE_M = 40.0
LIMITE_CARACTERES_LINHA_ROTULO = 22
LIMITE_CARACTERES_FORCAR_QUEBRA = 18

# Acima desta diferença entre a área da poligonal descrita e a área da
# geometria do bairro, a emissão avisa o analista: é o sintoma de perímetro
# com curvas mal resolvidas, que faz um documento fechar com área diferente
# do outro no mesmo processo.
TOLERANCIA_DIVERGENCIA_AREA_M2 = 5.0

# Quantos segmentos o Table Frame da planta A3 comporta sem estourar a área.
# Acima disso a tabela vira resumo e o Quadro completo vai em folha adicional.
LIMITE_LINHAS_TABELA_PLANTA = 35

# Último vértice exibido no Table Frame-resumo da planta A3.
LIMITE_RESUMO_TABELA_PLANTA = f'P-{LIMITE_LINHAS_TABELA_PLANTA:03d}'

# Título do documento anexo (o arquivo/layout seguem chamados de "quadro
# de coordenadas"; aqui é só o que o leitor vê no PDF).
TITULO_QUADRO = 'QUADRO DE CONFRONTAÇÕES'

# Aviso na planta quando o Quadro completo vai em folha adicional.
TEXTO_AVISO_TABELA_PLANTA = (
    'Tabela-resumo (até {limite}). O Quadro de Confrontações completo segue '
    'em anexo na Folha {folha_quadro}, em razão do espaço necessário à '
    'representação dos dados, nos termos do Art. 176 da Lei nº 6.015/73. '
    'A sequência integral de vértices consta também no Memorial Descritivo.'
)

# Texto do Termo de Autenticação. Delimita o que o selo prova, para não
# induzir quem recebe o documento a presumir conferência na origem.
TEXTO_ALCANCE_SELO = (
    'Este código de autenticação verifica a <b>integridade do conteúdo</b>: '
    'permite conferir que os dados geométricos descritos neste documento '
    '(vértices, coordenadas, azimutes, distâncias, confrontantes, área e '
    'perímetro) não foram alterados após a emissão. O código é derivado '
    'desses próprios dados, de modo que a reemissão a partir do mesmo '
    'levantamento produz o mesmo protocolo.'
)

TEXTO_LIMITE_SELO = (
    'O código <b>não constitui certidão registral</b> e <b>não substitui a '
    'assinatura digital</b> do responsável técnico. A geração é feita em '
    'estação de trabalho do analista, de modo que o código atesta a '
    'integridade dos dados, e não a origem institucional da emissão.'
)

# Aviso na planta quando a lista inteira coube no Table Frame.
TEXTO_TABELA_COMPLETA_PLANTA = (
    'Quadro de Confrontações completo nesta folha. A sequência integral de '
    'vértices consta também no Memorial Descritivo.'
)
