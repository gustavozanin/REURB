# -*- coding: utf-8 -*-
"""Auditoria de qualidade do PDF unificado (planta + quadro + memorial).

Uso (fora do ArcGIS Pro, com PyMuPDF instalado):

    python auditoria_qualidade.py caminho/do/arquivo.pdf

Checagens alinhadas ao plano de qualidade:
- vértices contínuos no quadro; fechamento P-n -> P-001
- soma das distâncias ≈ perímetro declarado
- área (shoelace) ≈ área declarada
- azimute/distância coerentes com coordenadas E/N
- rótulos P-xxx na planta (lista faltantes)
- todo confrontante do quadro com ao menos um rótulo no mapa
- nenhum rótulo de confrontante escrito dentro do perímetro
- presença do aviso da tabela-resumo (com o Art. 176 quando há anexo)
- Quadro de Confrontações logo após a planta, antes do memorial
- Termo de Autenticação fechando o pacote, com protocolo único
- segmentos curtos (< 15 m) ainda presentes (suspeitos)
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from math import atan2, degrees, hypot
from pathlib import Path

COMPRIMENTO_SUSPEITO_M = 15.0

# Título do anexo, em caixa alta, como sai no PDF do quadro. Na planta o
# mesmo nome aparece em caixa mista, então a busca é sensível a maiúsculas.
TITULO_QUADRO_PDF = 'QUADRO DE CONFRONTAÇÕES'
TEXTO_AVISO_ESPERADO = 'Tabela-resumo'
TEXTO_ART_176 = 'Art. 176'
TEXTO_TABELA_COMPLETA_ESPERADO = 'Quadro de Confrontações completo nesta folha'

TITULO_MEMORIAL_PDF = 'MEMORIAL DESCRITIVO'
TITULO_TERMO_PDF = 'TERMO DE AUTENTICAÇÃO'
PADRAO_PROTOCOLO = re.compile(r'ITERMA-\S+-\d{8}-[0-9A-F]{6}')


def parse_br(s: str) -> float:
    s = s.strip().replace(' ', '').rstrip('.,;')
    if ',' in s:
        return float(s.replace('.', '').replace(',', '.'))
    return float(s)


def parse_az(s: str):
    m = re.match(r"(\d+)°\s*(\d+)'\s*([\d.]+)\"", s.strip())
    if not m:
        return None
    return int(m.group(1)) + int(m.group(2)) / 60 + float(m.group(3)) / 3600


def extrair_linhas_quadro(texto: str):
    """Linhas da tabela de segmentos, na ordem De, Para, Azimute,
    Distância (m), Coord. E (x), Coord. N (y), Confrontantes — a mesma na
    tabela da planta e no Quadro de Confrontações.

    Varre o texto inteiro em vez de parar no primeiro token estranho,
    porque cabeçalho de coluna repetido e rodapé aparecem no meio da
    sequência quando a tabela ocupa mais de uma página.
    """
    tokens = [t.strip() for t in texto.splitlines() if t.strip()]
    numero = re.compile(r'[\d.,]+$')
    rows = []
    i = 0
    while i + 6 < len(tokens):
        de, para, az, dist, e, n, conf = tokens[i : i + 7]
        if (
            re.fullmatch(r'P-\d{3}', de)
            and re.fullmatch(r'P-\d{3}', para)
            and '°' in az
            and numero.match(dist)
            and numero.match(e)
            and numero.match(n)
        ):
            rows.append(
                {
                    'de': de,
                    'para': para,
                    'e': parse_br(e),
                    'n': parse_br(n),
                    'az': az,
                    'dist': parse_br(dist),
                    'conf': conf,
                }
            )
            i += 7
        else:
            i += 1
    return rows


def ocorrencias_no_mapa(pagina_dict, textos_aceitos):
    """Ocorrências dos textos informados no mapa da folha 1, com posição.

    A tabela-resumo repete os mesmos nomes numa coluna alinhada; essas
    ocorrências são descartadas por terem muitas linhas no mesmo X.

    Returns:
        list: pares `(texto, (x, y))` com o centro do texto na página.
    """
    candidatos = []
    for bloco in pagina_dict.get('blocks', []):
        for linha in bloco.get('lines', []):
            texto = ''.join(s['text'] for s in linha['spans']).strip()
            if texto in textos_aceitos:
                bbox = linha['bbox']
                centro = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                candidatos.append((texto, centro, round(bbox[0], 1)))

    colunas = Counter(x for _, _, x in candidatos)
    return [(texto, centro) for texto, centro, x in candidatos if colunas[x] <= 5]


def rotulos_confrontante_no_mapa(pagina_dict, nomes_conhecidos):
    """Nomes de confrontante desenhados no mapa da folha 1."""
    return [texto for texto, _ in ocorrencias_no_mapa(pagina_dict, nomes_conhecidos)]


def _ajuste_isotropico(pares):
    """Escala e deslocamento de UTM para página, sem rotação nem distorção.

    O mapa não é rotacionado, e o eixo Y da página cresce para baixo:
    `x = escala * E + desloc_x` e `y = -escala * N + desloc_y`.
    """
    media_e = sum(p[0][0] for p in pares) / len(pares)
    media_n = sum(p[0][1] for p in pares) / len(pares)
    media_x = sum(p[1][0] for p in pares) / len(pares)
    media_y = sum(p[1][1] for p in pares) / len(pares)
    numerador = denominador = 0.0
    for (e, n), (x, y) in pares:
        delta_e, delta_n = e - media_e, n - media_n
        numerador += delta_e * (x - media_x) - delta_n * (y - media_y)
        denominador += delta_e * delta_e + delta_n * delta_n
    if not denominador:
        return None
    escala = numerador / denominador
    if not escala:
        return None
    return escala, media_x - escala * media_e, media_y + escala * media_n


def transformacao_do_mapa(pagina_dict, coordenadas):
    """Casa os rótulos P-xxx do mapa com as coordenadas UTM do Quadro.

    Os rótulos têm um pequeno afastamento em relação ao vértice, então o
    ajuste é refeito algumas vezes descartando os piores resíduos, até
    sobrarem os pontos que definem a transformação com precisão.

    Returns:
        tuple: `(escala, desloc_x, desloc_y)`, ou None se houver poucos
        rótulos para estimar com segurança.
    """
    pares = [
        (coordenadas[texto], centro)
        for texto, centro in ocorrencias_no_mapa(pagina_dict, set(coordenadas))
    ]
    if len(pares) < 8:
        return None

    ativos = list(pares)
    ajuste = _ajuste_isotropico(ativos)
    for _ in range(6):
        if ajuste is None or len(ativos) <= 8:
            break
        escala, desloc_x, desloc_y = ajuste
        residuos = sorted(
            (
                hypot(escala * e + desloc_x - x, -escala * n + desloc_y - y),
                (e, n),
                (x, y),
            )
            for (e, n), (x, y) in ativos
        )
        ativos = [(item[1], item[2]) for item in residuos[: max(8, int(len(residuos) * 0.7))]]
        ajuste = _ajuste_isotropico(ativos)
    return ajuste


def _dentro_do_anel(ponto, anel):
    """Ponto em ponto interior ao anel, por contagem de cruzamentos."""
    x, y = ponto
    cruzamentos = 0
    for i in range(len(anel)):
        x1, y1 = anel[i]
        x2, y2 = anel[(i + 1) % len(anel)]
        if (y1 > y) != (y2 > y):
            if x1 + (y - y1) * (x2 - x1) / (y2 - y1) > x:
                cruzamentos += 1
    return cruzamentos % 2 == 1


def rotulos_dentro_do_perimetro(pagina_dict, linhas_quadro, folga_pt=1.0):
    """Rótulos de confrontante que caíram dentro da área do perímetro.

    O nome do confrontante descreve o que existe do lado de fora da
    divisa: escrito dentro da área, passa a ser lido como se fosse a
    própria gleba. A conferência reconstrói o perímetro em coordenadas de
    página e testa o centro de cada rótulo.

    Args:
        pagina_dict: `get_text('dict')` da folha 1.
        linhas_quadro: linhas do Quadro, na ordem dos vértices.
        folga_pt: quanto o centro precisa entrar para contar como erro,
            evitando acusar rótulo apenas encostado na linha.

    Returns:
        tuple: `(dentro, avaliados)` — lista de `(nome, distância em pt)` e
        quantos rótulos foram medidos. `(None, 0)` quando não foi possível
        reconstruir a geometria da página.
    """
    coordenadas = {linha['de']: (linha['e'], linha['n']) for linha in linhas_quadro}
    transformacao = transformacao_do_mapa(pagina_dict, coordenadas)
    if transformacao is None:
        return None, 0

    escala, desloc_x, desloc_y = transformacao
    anel = [
        (escala * linha['e'] + desloc_x, -escala * linha['n'] + desloc_y)
        for linha in linhas_quadro
    ]
    if len(anel) < 3:
        return None, 0

    nomes = {linha['conf'] for linha in linhas_quadro}
    dentro = []
    avaliados = 0
    for texto, centro in ocorrencias_no_mapa(pagina_dict, nomes):
        avaliados += 1
        if not _dentro_do_anel(centro, anel):
            continue
        distancia = min(
            _distancia_ao_segmento(centro, anel[i], anel[(i + 1) % len(anel)])
            for i in range(len(anel))
        )
        if distancia > folga_pt:
            dentro.append((texto, round(distancia, 1)))
    return dentro, avaliados


def _distancia_ao_segmento(ponto, inicio, fim):
    x, y = ponto
    x1, y1 = inicio
    x2, y2 = fim
    dx, dy = x2 - x1, y2 - y1
    if not dx and not dy:
        return hypot(x - x1, y - y1)
    posicao = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    posicao = max(0.0, min(1.0, posicao))
    return hypot(x - (x1 + posicao * dx), y - (y1 + posicao * dy))


def paginas_do_quadro(pages):
    """Índices das páginas do Quadro anexo.

    O título aparece só na primeira página do Quadro, então as páginas de
    continuação entram pela sequência: seguem contando enquanto trouxerem
    linhas da tabela e não começarem outra seção do pacote. Sem isso as
    continuações ficavam fora das checagens geométricas.

    Devolve lista vazia quando não há folha adicional (lista curta, que
    coube inteira na planta). A página 0 é sempre a planta e fica de fora.
    """
    indices = []
    dentro_do_quadro = False
    for i, texto in enumerate(pages):
        if not i:
            continue
        if TITULO_QUADRO_PDF in texto:
            dentro_do_quadro = True
        elif dentro_do_quadro:
            outra_secao = (
                TITULO_MEMORIAL_PDF in texto or TITULO_TERMO_PDF in texto
            )
            dentro_do_quadro = not outra_secao and bool(
                extrair_linhas_quadro(texto)
            )
        if dentro_do_quadro:
            indices.append(i)
    return indices


def auditar_pdf(caminho_pdf: Path) -> dict:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit(
            "Pacote 'pymupdf' necessário: pip install pymupdf"
        ) from exc

    doc = fitz.open(caminho_pdf)
    pages = [p.get_text('text') for p in doc]
    full = '\n'.join(pages)
    p1 = pages[0] if pages else ''
    p1_dict = doc[0].get_text('dict') if pages else {'blocks': []}

    indices_quadro = paginas_do_quadro(pages)
    tem_anexo = bool(indices_quadro)

    rows = []
    for page in ([pages[i] for i in indices_quadro] if tem_anexo else pages):
        rows.extend(extrair_linhas_quadro(page))
    seen = set()
    uniq = []
    for r in rows:
        if r['de'] in seen:
            continue
        seen.add(r['de'])
        uniq.append(r)
    # Ordena pelo número do vértice em vez de confiar na ordem de extração:
    # o Quadro imprime a lista em blocos lado a lado, e as checagens de
    # azimute e distância comparam cada linha com a seguinte.
    rows = sorted(uniq, key=lambda r: int(r['de'].split('-')[1]))

    issues = []
    info = {}

    if not rows:
        issues.append('Quadro sem linhas parseáveis.')
        return {'ok': False, 'issues': issues, 'info': info}

    nums = [int(r['de'].split('-')[1]) for r in rows]
    missing = [i for i in range(1, max(nums) + 1) if i not in nums]
    info['vertices'] = len(rows)
    if missing:
        issues.append(f'Vertices faltando no quadro: {missing}')

    peri = sum(r['dist'] for r in rows)
    m_peri = re.search(r'Perímetro:\s*([\d.,]+)\s*m', full)
    peri_decl = parse_br(m_peri.group(1)) if m_peri else None
    info['perimetro_soma'] = round(peri, 4)
    info['perimetro_declarado'] = peri_decl
    if peri_decl is not None and abs(peri - peri_decl) > 0.05:
        issues.append(
            f'Perímetro divergente: soma={peri:.4f} declarado={peri_decl}'
        )

    verts = {r['de']: (r['e'], r['n']) for r in rows}
    dests = [
        rows[i + 1]['de'] if i + 1 < len(rows) else 'P-001'
        for i in range(len(rows))
    ]
    errs_d = errs_az = 0
    for i, r in enumerate(rows):
        e1, n1 = verts[r['de']]
        e2, n2 = verts[dests[i]]
        if abs(hypot(e2 - e1, n2 - n1) - r['dist']) > 0.005:
            errs_d += 1
        az = (degrees(atan2(e2 - e1, n2 - n1)) + 360) % 360
        az_dec = parse_az(r['az'])
        if az_dec is None or abs(((az - az_dec + 180) % 360) - 180) > 0.01:
            errs_az += 1
    info['erros_distancia'] = errs_d
    info['erros_azimute'] = errs_az
    if errs_d:
        issues.append(f'{errs_d} segmento(s) com distância incoerente.')
    if errs_az:
        issues.append(f'{errs_az} segmento(s) com azimute incoerente.')

    coords = [(r['e'], r['n']) for r in rows]
    coords_c = coords + [coords[0]]
    area = 0.0
    for i in range(len(coords)):
        x1, y1 = coords_c[i]
        x2, y2 = coords_c[i + 1]
        area += x1 * y2 - x2 * y1
    area = abs(area) / 2
    m_area = re.search(r'Área:\s*([\d.,]+)\s*m', full)
    area_decl = parse_br(m_area.group(1)) if m_area else None
    info['area_shoelace'] = round(area, 2)
    info['area_declarada'] = area_decl
    if area_decl is not None and abs(area - area_decl) > 0.5:
        issues.append(f'Área divergente: shoelace={area:.2f} declarado={area_decl}')

    labels = set(re.findall(r'P-\d{3}', p1))
    allv = {f'P-{i:03d}' for i in range(1, max(nums) + 1)}
    faltantes = sorted(allv - labels)
    info['rotulos_planta_faltantes'] = faltantes
    if faltantes:
        issues.append(f'Rótulos ausentes na planta: {faltantes}')

    p1_lower = p1.lower()
    info['quadro_em_anexo'] = tem_anexo
    if tem_anexo:
        info['paginas_do_quadro'] = [i + 1 for i in indices_quadro]
        tem_aviso = (
            TEXTO_AVISO_ESPERADO.lower() in p1_lower
            and TEXTO_ART_176.lower() in p1_lower
        )
        if not tem_aviso:
            issues.append(
                'Aviso do Quadro em anexo (tabela-resumo + Art. 176 da Lei '
                '6.015/73) não encontrado na planta (verifique o TextElement '
                '{aviso_tabela} no layout).'
            )
        if indices_quadro[0] != 1:
            issues.append(
                'Quadro de Confrontações fora de ordem: deve vir logo após a '
                f'planta (começa na página {indices_quadro[0] + 1}).'
            )
    else:
        tem_aviso = TEXTO_TABELA_COMPLETA_ESPERADO.lower() in p1_lower
        if not tem_aviso:
            issues.append(
                'Sem folha adicional, mas o aviso de quadro completo não foi '
                'encontrado na planta (verifique o TextElement {aviso_tabela}).'
            )
    info['aviso_tabela'] = tem_aviso

    nomes_quadro = {r['conf'] for r in rows}
    rotulos_mapa = rotulos_confrontante_no_mapa(p1_dict, nomes_quadro)
    contagem_mapa = Counter(rotulos_mapa)
    sem_rotulo = sorted(nomes_quadro - set(rotulos_mapa))
    info['rotulos_confrontante_no_mapa'] = contagem_mapa.most_common()
    info['confrontantes_sem_rotulo_no_mapa'] = sem_rotulo
    if sem_rotulo:
        issues.append(
            f'Confrontante(s) sem rótulo no mapa da planta: {sem_rotulo}'
        )

    dentro_perimetro, rotulos_medidos = rotulos_dentro_do_perimetro(p1_dict, rows)
    info['rotulos_confrontante_medidos'] = rotulos_medidos
    if dentro_perimetro is None:
        info['rotulos_dentro_do_perimetro'] = 'não avaliado'
    else:
        info['rotulos_dentro_do_perimetro'] = dentro_perimetro
        if dentro_perimetro:
            detalhe = ', '.join(
                f'{nome} ({distancia} pt para dentro)'
                for nome, distancia in dentro_perimetro
            )
            issues.append(
                'Rótulo(s) de confrontante escrito(s) dentro do perímetro, '
                f'onde passam a ser lidos como a própria gleba: {detalhe}'
            )

    indices_termo = [i for i, t in enumerate(pages) if TITULO_TERMO_PDF in t]
    info['termo_autenticacao'] = bool(indices_termo)
    if not indices_termo:
        issues.append(
            'Termo de Autenticação ausente: o pacote deve terminar com a '
            'folha do selo (protocolo + código de conteúdo).'
        )
    else:
        if indices_termo[-1] != len(pages) - 1:
            issues.append(
                'Termo de Autenticação fora de ordem: deve ser a última '
                'folha do pacote.'
            )
        protocolos = set(PADRAO_PROTOCOLO.findall(full))
        info['protocolo'] = sorted(protocolos)
        if not protocolos:
            issues.append('Protocolo não encontrado no pacote.')
        elif len(protocolos) > 1:
            issues.append(f'Protocolos divergentes no pacote: {sorted(protocolos)}')
        elif not PADRAO_PROTOCOLO.search(p1):
            issues.append(
                'Protocolo ausente na planta (verifique o TextElement '
                '{protocolo} no layout).'
            )

    curtos = [
        f"{r['de']} ({r['dist']:.2f} m) {r['conf']}"
        for r in rows
        if r['dist'] < COMPRIMENTO_SUSPEITO_M
    ]
    info['segmentos_curtos'] = curtos
    info['confrontantes'] = Counter(r['conf'] for r in rows).most_common()

    az_sem_zero = [
        r['az'] for r in rows if re.search(r"°\s*\d'", r['az'])
    ]
    info['azimutes_minuto_1digito'] = len(az_sem_zero)
    if az_sem_zero:
        issues.append(
            f'{len(az_sem_zero)} azimute(s) com minuto sem zero à esquerda.'
        )

    return {
        'ok': not issues,
        'issues': issues,
        'info': info,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Auditoria de qualidade do PDF da ferramenta memorial.'
    )
    parser.add_argument('pdf', type=Path, help='Caminho do PDF unificado')
    args = parser.parse_args(argv)
    if not args.pdf.exists():
        print(f'Arquivo não encontrado: {args.pdf}', file=sys.stderr)
        return 2

    resultado = auditar_pdf(args.pdf)
    print(f"PDF: {args.pdf}")
    print(f"OK: {resultado['ok']}")
    for chave, valor in resultado['info'].items():
        print(f'  {chave}: {valor}')
    if resultado['issues']:
        print('Problemas:')
        for issue in resultado['issues']:
            print(f'  - {issue}')
        return 1
    print('Nenhum problema encontrado nas checagens automatizadas.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
