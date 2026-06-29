# -*- coding: utf-8 -*-

import ast
import json


def validar_json(json_texto: str) -> str:
    """
    Valida o JSON de entrada e retorna o número do processo coletivo.

    Args:
        json_texto: String JSON com o campo numeroProcessoColetivo.

    Returns:
        Número do processo coletivo (n_coletivo).

    Raises:
        ValueError: Se o JSON for inválido ou o campo obrigatório estiver ausente.
    """
    if json_texto is None or not str(json_texto).strip():
        raise ValueError('JSON de entrada vazio')

    texto = str(json_texto).strip()
    try:
        dados = json.loads(texto.replace("'", ''))
    except json.JSONDecodeError:
        try:
            dados = ast.literal_eval(texto)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(f'JSON de entrada inválido: {exc}') from exc

    if not isinstance(dados, dict):
        raise ValueError('JSON de entrada deve ser um objeto')

    numero = dados.get('numeroProcessoColetivo')
    if numero is None:
        raise ValueError("Campo 'numeroProcessoColetivo' ausente no JSON de entrada")

    numero = str(numero).strip()
    if not numero:
        raise ValueError("Campo 'numeroProcessoColetivo' não pode ser vazio")

    return numero
