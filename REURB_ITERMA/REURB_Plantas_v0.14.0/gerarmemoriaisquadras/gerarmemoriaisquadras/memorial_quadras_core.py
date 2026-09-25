# -*- coding: utf-8 -*-
"""Funções puras e testáveis do memorial de quadras."""
import math
import re
import unicodedata


def _par_xy(valor):
    if not isinstance(valor, (list, tuple)) or len(valor) < 2:
        return None
    if isinstance(valor[0], (int, float)) and isinstance(valor[1], (int, float)):
        return float(valor[0]), float(valor[1])
    return None


def _fim_curva(obj):
    if not isinstance(obj, dict):
        return None
    for chave in ('a', 'b', 'c'):
        trecho = obj.get(chave)
        if trecho:
            return _par_xy(trecho[0])
    return None


def pontos_controle_de_geojson(dados):
    """Anéis com os vértices de edição do projeto (sem densificar o arco)."""
    dados = dados or {}
    aneis = []
    for chave in ('curveRings', 'rings'):
        for anel in dados.get(chave) or []:
            pts = []
            for item in anel:
                if isinstance(item, dict):
                    fim = _fim_curva(item)
                    if fim:
                        pts.append(fim)
                else:
                    xy = _par_xy(item)
                    if xy:
                        pts.append(xy)
            if pts:
                aneis.append(pts)
        if aneis:
            break
    return aneis


def slug(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode(
        "ascii", "ignore"
    ).decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_").lower() or "valor"


def epsg_sirgas_2000_utm(longitude, latitude):
    zona = max(18, min(25, int((float(longitude) + 180) // 6) + 1))
    return (31972 if float(latitude) >= 0 else 31978) + zona - 18


def azimute_gms(delta_e, delta_n):
    total = int(round(
        ((math.degrees(math.atan2(delta_e, delta_n)) + 360) % 360) * 3600
    )) % 1296000
    graus, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f'{graus:03d}°{minutos:02d}\'{segundos:02d}"'


def segmentos_de_aneis(aneis, prefixo="Q-P", tolerancia=0.001):
    resultado, numero = [], 1
    for parte, anel in enumerate(aneis, 1):
        pontos = [(float(x), float(y)) for x, y in anel]
        if (
            len(pontos) > 1
            and math.hypot(
                pontos[0][0] - pontos[-1][0], pontos[0][1] - pontos[-1][1]
            ) <= tolerancia
        ):
            pontos.pop()
        if len(pontos) < 3:
            continue
        nomes = [f"{prefixo}{numero + i:03d}" for i in range(len(pontos))]
        for i, (e1, n1) in enumerate(pontos):
            e2, n2 = pontos[(i + 1) % len(pontos)]
            distancia = math.hypot(e2 - e1, n2 - n1)
            if distancia <= tolerancia:
                continue
            resultado.append({
                "vertice": nomes[i],
                "vertice_para": nomes[(i + 1) % len(pontos)],
                "parte": parte,
                "ordem": i + 1,
                "eLong": e1,
                "nLat": n1,
                "este_para": e2,
                "norte_para": n2,
                "azimute": azimute_gms(e2 - e1, n2 - n1),
                "distancia": distancia,
            })
        numero += len(pontos)
    return resultado


def auditoria(segmentos, perimetro_geometria, tolerancia_m=0.05):
    soma = sum(float(x["distancia"]) for x in segmentos)
    diferenca = abs(soma - float(perimetro_geometria or 0))
    return {
        "segmentos": len(segmentos),
        "somaDistanciasM": round(soma, 4),
        "perimetroGeometriaM": round(float(perimetro_geometria or 0), 4),
        "diferencaFechamentoM": round(diferenca, 4),
        "aprovada": diferenca <= tolerancia_m,
    }
