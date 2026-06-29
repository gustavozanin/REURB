# -*- coding: utf-8 -*-


def escapar_sql(valor: str) -> str:
    """Escapa aspas simples para uso em cláusulas WHERE do ArcGIS."""
    return str(valor).replace("'", "''")


def clausula_n_coletivo(numero_reurb_coletivo: str) -> str:
    """Monta cláusula WHERE para filtrar por n_coletivo."""
    return f"n_coletivo = '{escapar_sql(numero_reurb_coletivo)}'"
