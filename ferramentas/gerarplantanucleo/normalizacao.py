# -*- coding: utf-8 -*-

CASAS_DECIMAIS = 4


def arredondar_4(valor):
    if valor is None or valor == "":
        return valor
    return round(float(valor), CASAS_DECIMAIS)


def decimal_texto(valor):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):.{CASAS_DECIMAIS}f}".replace(".", ",")
