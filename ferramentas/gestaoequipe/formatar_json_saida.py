# -*- coding: utf-8 -*-

import json


def formatar_json_saida(quadras: list) -> str:
    """
    Formata o resultado da gestão de equipe como JSON de saída.

    Args:
        quadras: Lista de dicionários por quadra retornada por calcular_gestao_equipe.

    Returns:
        String JSON no contrato de saída da ferramenta.
    """
    payload = {
        'dados': {
            'quadras': quadras
        }
    }
    return json.dumps(payload, ensure_ascii=False)
