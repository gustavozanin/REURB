# -*- coding: utf-8 -*-

import csv
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLUNAS = ["De", "Para", "Azim.", "Dist.", "Coord. E", "Coord. N"]
LARGURAS = [72, 72, 150, 92, 118, 126]
LINHAS_POR_BLOCO = 31
MARGEM = 24
ESPACO_BLOCOS = 26
ALTURA_LINHA = 28
ALTURA_TITULO = 64
ALTURA_RODAPE = 30
NOTA_RODAPE = (
    "ATENÇÃO: Este anexo corresponde aos vértices simplificados exibidos na planta principal. "
    "A sequência analítica completa do perímetro encontra-se no Memorial Descritivo."
)


def fonte(tamanho, negrito=False):
    candidatos = [
        r"C:\Windows\Fonts\arialbd.ttf" if negrito else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if negrito else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for candidato in candidatos:
        if Path(candidato).exists():
            return ImageFont.truetype(candidato, tamanho)
    return ImageFont.load_default()


def ler_csv(caminho_csv):
    with open(caminho_csv, "r", encoding="utf-8-sig", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo, delimiter=";"))

    total = len(linhas)
    saida = []
    for indice, linha in enumerate(linhas):
        de = linha.get("De", "")
        para = linhas[(indice + 1) % total].get("De", "") if total else ""
        saida.append([
            de,
            para,
            linha.get("Azimute", ""),
            linha.get("Distancia (m)", ""),
            linha.get("E", ""),
            linha.get("N", ""),
        ])
    return saida


def desenhar_celula(draw, xy, texto, font, fill=(255, 255, 255), outline=(0, 0, 0), bold=False):
    x1, y1, x2, y2 = xy
    draw.rectangle(xy, fill=fill, outline=outline, width=2 if bold else 1)
    bbox = draw.textbbox((0, 0), str(texto), font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 1), str(texto), fill=(0, 0, 0), font=font)


def gerar_png(caminho_csv, caminho_png=None, titulo=None):
    caminho_csv = Path(caminho_csv)
    linhas = ler_csv(caminho_csv)
    if caminho_png is None:
        caminho_png = caminho_csv.with_name(caminho_csv.stem.replace("quadro_coordenadas", "quadro_vertices_prancha_completo") + ".png")
    caminho_png = Path(caminho_png)

    blocos = [linhas[i:i + LINHAS_POR_BLOCO] for i in range(0, len(linhas), LINHAS_POR_BLOCO)] or [[]]
    largura_bloco = sum(LARGURAS)
    altura_bloco = ALTURA_LINHA * (LINHAS_POR_BLOCO + 1)
    largura = MARGEM * 2 + len(blocos) * largura_bloco + (len(blocos) - 1) * ESPACO_BLOCOS
    altura = MARGEM * 2 + ALTURA_TITULO + altura_bloco + ALTURA_RODAPE

    imagem = Image.new("RGB", (largura, altura), "white")
    draw = ImageDraw.Draw(imagem)
    fonte_titulo = fonte(13, True)
    fonte_meta = fonte(10)
    fonte_head = fonte(12, True)
    fonte_corpo = fonte(11)
    fonte_rodape = fonte(9)

    if titulo is None:
        titulo = "Quadro de Coordenadas da Planta"
    linhas_titulo = str(titulo).split(" | ")
    if len(linhas_titulo) > 1:
        linhas_titulo = [
            linhas_titulo[0],
            " | ".join(linhas_titulo[1:3]),
            " | ".join(linhas_titulo[3:]),
        ]
        linhas_titulo = [linha for linha in linhas_titulo if linha]
    for indice, linha in enumerate(linhas_titulo):
        draw.text((MARGEM, MARGEM + indice * 18), linha, fill=(0, 0, 0), font=fonte_titulo if indice == 0 else fonte_meta)

    y0 = MARGEM + ALTURA_TITULO
    for indice_bloco, bloco in enumerate(blocos):
        x0 = MARGEM + indice_bloco * (largura_bloco + ESPACO_BLOCOS)
        x = x0
        for col, largura_col in zip(COLUNAS, LARGURAS):
            desenhar_celula(draw, (x, y0, x + largura_col, y0 + ALTURA_LINHA), col, fonte_head, fill=(210, 210, 210), bold=True)
            x += largura_col

        for indice_linha in range(LINHAS_POR_BLOCO):
            y = y0 + ALTURA_LINHA * (indice_linha + 1)
            valores = bloco[indice_linha] if indice_linha < len(bloco) else [""] * len(COLUNAS)
            x = x0
            for valor, largura_col in zip(valores, LARGURAS):
                desenhar_celula(draw, (x, y, x + largura_col, y + ALTURA_LINHA), valor, fonte_corpo)
                x += largura_col

    y_rodape = y0 + altura_bloco + 10
    draw.text((MARGEM, y_rodape), NOTA_RODAPE, fill=(70, 70, 70), font=fonte_rodape)

    imagem.save(caminho_png)
    return caminho_png


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Uso: python gerar_png_quadro_coordenadas.py quadro.csv [saida.png]")
    saida = gerar_png(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
    print(saida)
