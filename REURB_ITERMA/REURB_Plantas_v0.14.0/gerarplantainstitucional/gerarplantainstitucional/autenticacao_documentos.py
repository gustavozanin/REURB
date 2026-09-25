# -*- coding: utf-8 -*-
"""Selo de autenticação dos documentos gerados localmente.

O que este módulo faz e o que não faz
-------------------------------------
Ele sela o *conteúdo geométrico* da emissão (vértices, coordenadas,
azimutes, distâncias, confrontantes, área e perímetro) com um hash
SHA-256, e deriva daí um número de protocolo associado ao `n_coletivo`
do processo REURB. Isso permite conferir que os dados descritos no
documento não foram alterados depois de emitidos.

Não prova autoria: como a geração roda na máquina do analista, qualquer
cópia da ferramenta produz um selo igualmente válido. Provar que o ITERMA
emitiu o documento exige registrar a emissão em um ponto central, o que
depende de infraestrutura ainda não definida.

Por que selar o conteúdo e não o PDF: o protocolo é impresso dentro do
próprio PDF, então o hash do binário mudaria no momento em que o selo
entra nele. Selar o conteúdo também mantém o selo válido ao reemitir a
planta a partir do mesmo levantamento. Os hashes dos arquivos entregues
(CSV e ZIP) vão listados no Termo de Autenticação, para quem quiser
conferir arquivo a arquivo.

Lógica pura, sem ArcPy — testável em `test_qualidade_unitario.py`.
"""

import hashlib

from constantes import CONFRONTANTE_PADRAO

# Quantos dígitos hex do hash entram no sufixo do protocolo. Seis dá 16,7
# milhões de combinações: suficiente para não colidir entre emissões do
# mesmo processo no mesmo dia, mantendo o número legível/ditável.
DIGITOS_SUFIXO_PROTOCOLO = 6

PREFIXO_PROTOCOLO = 'ITERMA'


def _numero(valor, casas=4):
    """Formata número com casas fixas para o hash não variar por arredondamento."""
    try:
        return f'{float(valor):.{casas}f}'
    except (TypeError, ValueError):
        return ''


def texto_canonico(segmentos, meta):
    """
    Monta a representação textual estável do conteúdo da emissão.

    É essa string que vira o hash, então ela precisa ser reproduzível:
    mesmos dados de entrada, mesmo texto, independentemente da ordem em
    que os dicts foram montados ou de formatação de exibição.

    Args:
        segmentos: lista de segmentos (ver `formatar_dados_perimetro`).
        meta: metadados da emissão (numero_reurb, bairro, municipio,
            area_m2, perimetro_m, fuso).

    Returns:
        str: linhas `campo=valor` do cabeçalho, seguidas de uma linha por
        segmento no formato `vertice|E|N|azimute|distancia|confrontante`.
    """
    cabecalho = [
        f"processo={str(meta.get('numero_reurb') or '').strip()}",
        f"bairro={str(meta.get('bairro') or '').strip()}",
        f"municipio={str(meta.get('municipio') or '').strip()}",
        f"fuso={str(meta.get('fuso') or '').strip()}",
        f"area={_numero(meta.get('area_m2'), 2)}",
        f"perimetro={_numero(meta.get('perimetro_m'), 2)}",
        f'segmentos={len(segmentos)}',
    ]
    linhas = [
        '|'.join([
            str(item.get('vertice') or '').strip(),
            _numero(item.get('eLong')),
            _numero(item.get('nLat')),
            str(item.get('azimute') or '').strip(),
            _numero(item.get('distancia')),
            str(item.get('confrontante') or CONFRONTANTE_PADRAO).strip(),
        ])
        for item in segmentos
    ]
    return '\n'.join(cabecalho + linhas)


def hash_conteudo(segmentos, meta):
    """SHA-256 (hex) do conteúdo canônico da emissão."""
    return hashlib.sha256(
        texto_canonico(segmentos, meta).encode('utf-8')
    ).hexdigest()


def hash_arquivo(caminho, bloco=1024 * 1024):
    """SHA-256 (hex) de um arquivo entregue; '' se ele não existir."""
    digest = hashlib.sha256()
    try:
        with open(caminho, 'rb') as arquivo:
            for pedaco in iter(lambda: arquivo.read(bloco), b''):
                digest.update(pedaco)
    except OSError:
        return ''
    return digest.hexdigest()


def montar_protocolo(numero_reurb, hash_hex, data_emissao):
    """
    Monta o número de protocolo da emissão.

    Formato `ITERMA-<processo>-<AAAAMMDD>-<6 hex>`. O sufixo vem do hash,
    então o número é determinístico (mesma emissão, mesmo protocolo) e
    único na prática sem precisar de contador central, que colidiria entre
    analistas trabalhando em paralelo.

    Args:
        numero_reurb: número do processo REURB coletivo (`n_coletivo`).
        hash_hex: hash do conteúdo (ver `hash_conteudo`).
        data_emissao: `datetime.date`/`datetime` da emissão.

    Returns:
        str: o protocolo.
    """
    sufixo = hash_hex[:DIGITOS_SUFIXO_PROTOCOLO].upper()
    return (
        f'{PREFIXO_PROTOCOLO}-{str(numero_reurb).strip()}-'
        f"{data_emissao.strftime('%Y%m%d')}-{sufixo}"
    )


def montar_selo(segmentos, meta, data_emissao, arquivos=None):
    """
    Monta o selo completo da emissão, pronto para imprimir nos documentos.

    Args:
        segmentos: segmentos do perímetro.
        meta: metadados da emissão (ver `texto_canonico`).
        data_emissao: data/hora da geração.
        arquivos: dict opcional {rótulo: caminho} dos artefatos já
            gravados (CSV, ZIP) para listar o hash de cada um.

    Returns:
        dict: `protocolo`, `hash_conteudo`, `emitido_em` e
        `hashes_arquivos` ({rótulo: hash}).
    """
    digest = hash_conteudo(segmentos, meta)
    return {
        'protocolo': montar_protocolo(
            meta.get('numero_reurb'), digest, data_emissao
        ),
        'hash_conteudo': digest,
        'emitido_em': data_emissao.strftime('%d/%m/%Y %H:%M'),
        'hashes_arquivos': {
            rotulo: hash_arquivo(caminho)
            for rotulo, caminho in (arquivos or {}).items()
        },
    }
