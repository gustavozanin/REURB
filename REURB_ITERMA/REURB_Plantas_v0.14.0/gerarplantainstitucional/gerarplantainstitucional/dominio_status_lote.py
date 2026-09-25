# -*- coding: utf-8 -*-
"""Domínio do status do lote — identificação de imóveis institucionais.

Aceita código ou texto. Textos canônicos (spec):
  - Institucional Municipal
  - Institucional Estadual

O mapa código→rótulo vem do domínio da camada (quando disponível) ou
pode ser passado nos testes como dict simples.
"""

from __future__ import annotations

ROTULOS_INSTITUCIONAIS = (
    'Institucional Municipal',
    'Institucional Estadual',
)


def _normalizar(texto: str) -> str:
    return ' '.join(str(texto or '').strip().lower().split())


def _rotulos_normalizados() -> set[str]:
    return {_normalizar(r) for r in ROTULOS_INSTITUCIONAIS}


def rotulo_do_valor(valor, mapa_dominio: dict | None = None) -> str:
    """Resolve valor bruto (código ou texto) para rótulo legível."""
    if valor is None:
        return ''
    mapa = mapa_dominio or {}
    # Código numérico ou string de código presente no mapa
    if valor in mapa:
        return str(mapa[valor])
    chave_str = str(valor).strip()
    if chave_str in mapa:
        return str(mapa[chave_str])
    try:
        chave_int = int(chave_str)
        if chave_int in mapa:
            return str(mapa[chave_int])
    except (TypeError, ValueError):
        pass
    return chave_str


def eh_institucional(valor, mapa_dominio: dict | None = None) -> bool:
    """True se o status (código ou texto) for Municipal ou Estadual."""
    rotulo = rotulo_do_valor(valor, mapa_dominio)
    if _normalizar(rotulo) in _rotulos_normalizados():
        return True
    # Valor já é o texto institucional sem mapa
    if _normalizar(valor) in _rotulos_normalizados():
        return True
    # Rótulo do domínio contém o texto canônico (ex.: "13 - Institucional Municipal")
    rot_n = _normalizar(rotulo)
    for alvo in _rotulos_normalizados():
        if alvo in rot_n:
            return True
    return False
