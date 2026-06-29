# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


COLUNAS = ["De", "Para", "Azim.", "Dist.", "Coord. E", "Coord. N"]
LARGURAS = [76, 76, 170, 102, 132, 150]
MARGEM = 26
ALTURA_TITULO = 66
ALTURA_LINHA = 32
ALTURA_RODAPE = 34


def _decimal_texto(valor):
    if valor is None or valor == "":
        return ""
    return f"{float(valor):.4f}".replace(".", ",")


def _fonte(tamanho, negrito=False):
    candidatos = [
        r"C:\Windows\Fonts\arialbd.ttf" if negrito else r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibrib.ttf" if negrito else r"C:\Windows\Fonts\calibri.ttf",
    ]
    for candidato in candidatos:
        if Path(candidato).exists():
            return ImageFont.truetype(candidato, tamanho)
    return ImageFont.load_default()


def _desenhar_celula(draw, xy, texto, font, fill=(255, 255, 255), width=2):
    x1, y1, x2, y2 = xy
    draw.rectangle(xy, fill=fill, outline=(0, 0, 0), width=width)
    texto = "" if texto is None else str(texto)
    bbox = draw.textbbox((0, 0), texto, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        (x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 1),
        texto,
        fill=(0, 0, 0),
        font=font,
    )


def _linhas(dados_perimetro):
    total = len(dados_perimetro)
    linhas = []
    for indice, item in enumerate(dados_perimetro):
        de = item.get("vertice", "")
        para = dados_perimetro[(indice + 1) % total].get("vertice", "") if total else ""
        linhas.append([
            de,
            para,
            item.get("azimute", ""),
            _decimal_texto(item.get("distancia", "")),
            _decimal_texto(item.get("eLong", "")),
            _decimal_texto(item.get("nLat", "")),
        ])
    return linhas


def gerar_png(dados_perimetro, numero_reurb_coletivo, caminho_png, titulo=None):
    caminho_png = Path(caminho_png)
    caminho_png.parent.mkdir(parents=True, exist_ok=True)
    linhas = _linhas(dados_perimetro)
    titulo = titulo or f"Quadro de Coordenadas Completo - {numero_reurb_coletivo}"

    largura = MARGEM * 2 + sum(LARGURAS)
    altura_tabela = ALTURA_LINHA * (len(linhas) + 1)
    altura = MARGEM * 2 + ALTURA_TITULO + altura_tabela + ALTURA_RODAPE

    imagem = Image.new("RGB", (largura, altura), "white")
    draw = ImageDraw.Draw(imagem)
    fonte_titulo = _fonte(24, True)
    fonte_head = _fonte(20, True)
    fonte_corpo = _fonte(19)
    fonte_rodape = _fonte(9)

    draw.text((8, MARGEM), titulo, fill=(0, 0, 0), font=fonte_titulo)

    y0 = MARGEM + ALTURA_TITULO
    x = MARGEM
    for coluna, largura_coluna in zip(COLUNAS, LARGURAS):
        _desenhar_celula(
            draw,
            (x, y0, x + largura_coluna, y0 + ALTURA_LINHA),
            coluna,
            fonte_head,
            fill=(210, 210, 210),
            width=2,
        )
        x += largura_coluna

    for indice_linha, valores in enumerate(linhas):
        y = y0 + ALTURA_LINHA * (indice_linha + 1)
        x = MARGEM
        for valor, largura_coluna in zip(valores, LARGURAS):
            _desenhar_celula(
                draw,
                (x, y, x + largura_coluna, y + ALTURA_LINHA),
                valor,
                fonte_corpo,
                width=2,
            )
            x += largura_coluna

    rodape = "ATENÇÃO: Este quadro corresponde à sequência completa de vértices utilizada no Memorial Descritivo."
    draw.text((MARGEM, y0 + altura_tabela + 12), rodape, fill=(70, 70, 70), font=fonte_rodape)
    imagem.save(caminho_png)
    return caminho_png


def gerar_por_json(json_path, caminho_png=None):
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    identificacao = data["identificacaoPlanilha"]
    numero = identificacao["numeroProcessoColetivo"]
    dados = identificacao["perimetros"][0]["dadosPerimetro"]

    if caminho_png is None:
        nome_base = numero.replace("/", "_")
        caminho_png = json_path.with_name(f"quadro_vertices_completo_{nome_base}.png")

    titulo = f"Quadro de Coordenadas Completo - {numero}"
    return gerar_png(dados, numero, caminho_png, titulo=titulo)


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Uso: python gerar_png_quadro_vertices_completo.py resultado.json [saida.png]")
    saida = gerar_por_json(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else None)
    print(saida)
