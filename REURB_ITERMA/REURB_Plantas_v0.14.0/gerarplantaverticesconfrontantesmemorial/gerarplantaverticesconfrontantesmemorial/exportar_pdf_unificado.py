# -*- coding: utf-8 -*-
"""Exportação de layout para PDF e união dos PDFs parciais na ordem final.

Ordem fixa do pacote: Planta -> Quadro(s) -> Memorial(is). O Quadro vem logo
depois da planta porque é folha adicional dela (ver `planejar_folhas`); o
memorial é documento à parte e não entra na contagem de folhas.

`montar_ordem_pdfs` e `planejar_folhas` são lógica pura (sem ArcPy), testáveis
isoladamente (ver `test_qualidade_unitario.py`). `exportar_pdf_layout` e
`unir_pdfs` são wrappers ArcPy finos, usados também por
`gerar_planta_perimetro.py` e `memorial_narrativo.py` (via
`preencher_layout_memorial`) para não duplicar a chamada de
`exportToPDF`/`PDFDocumentCreate` em cada módulo.
"""

import os

from constantes import LIMITE_LINHAS_TABELA_PLANTA

try:
    import arcpy
except ImportError:
    arcpy = None


def planejar_folhas(total_segmentos, limite=LIMITE_LINHAS_TABELA_PLANTA):
    """
    Decide se o Quadro de Confrontações vai como folha adicional da planta e
    devolve os rótulos de folha do carimbo. Lógica pura, sem ArcPy.

    Cabendo a lista inteira no Table Frame da planta, o pacote tem uma folha
    só ('Única') e o Quadro não é anexado. Estourando o limite, a planta vira
    'Folha 01/02' e o Quadro anexo 'Folha 02/02' — o Quadro conta como uma
    folha, mesmo que a lista precise de mais de uma página (a paginação
    interna dele fica no rodapé, ver `documentos_pdf.gerar_quadro`).

    Args:
        total_segmentos: quantidade de segmentos do perímetro.
        limite: quantos segmentos o Table Frame da planta comporta.

    Returns:
        dict: `tem_anexo` (bool), `folha_planta` (str), `folha_quadro` (str ou
        None) e `total_folhas` (int).
    """
    tem_anexo = int(total_segmentos or 0) > int(limite)
    if not tem_anexo:
        return {
            'tem_anexo': False,
            'folha_planta': 'Única',
            'folha_quadro': None,
            'total_folhas': 1,
        }
    return {
        'tem_anexo': True,
        'folha_planta': '01/02',
        'folha_quadro': '02/02',
        'total_folhas': 2,
    }


def exportar_pdf_layout(layout, path):
    """
    Helper fino: exporta um layout já pronto (map frames/tabelas/textos
    preenchidos) para PDF.

    Args:
        layout: objeto `arcpy._mp.Layout`.
        path: caminho do arquivo `.pdf` de saída.

    Returns:
        os.PathLike: o próprio `path`.

    Raises:
        RuntimeError: se ArcPy não estiver disponível neste ambiente.
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')

    layout.exportToPDF(out_pdf=path)
    return path


def montar_ordem_pdfs(planta, quadros, memoriais, termo=None):
    """
    Monta a lista ordenada de PDFs parciais do pacote final: Planta ->
    Quadro(s) -> Memorial(is) -> Termo de Autenticação. Lógica pura, sem
    ArcPy.

    Args:
        planta: caminho (str) do PDF da planta, ou None/'' se ainda não
            gerado.
        quadros: caminho único (str) ou lista de caminhos dos PDFs do
            Quadro de Confrontações; None/'' quando a lista coube inteira
            na planta e não há folha adicional (ver `planejar_folhas`).
        memoriais: caminho único (str) ou lista de caminhos dos PDFs do
            memorial (uma folha ou várias, ver
            `memorial_narrativo.preencher_layout_memorial`).
        termo: caminho do PDF do Termo de Autenticação, que fecha o
            pacote; None quando a emissão não é selada.

    Returns:
        list[str]: ordem fixa Planta -> Quadro(s) -> Memorial(is) ->
        Termo, sem entradas vazias/None.

    Raises:
        ValueError: se a lista resultante ficar vazia (nenhum PDF
            informado em nenhuma das três partes).
    """

    def _normalizar(valor):
        if not valor:
            return []
        if isinstance(valor, (list, tuple)):
            return [str(item) for item in valor if item]
        return [str(valor)]

    ordem = (
        _normalizar(planta)
        + _normalizar(quadros)
        + _normalizar(memoriais)
        + _normalizar(termo)
    )
    if not ordem:
        raise ValueError(
            'Nenhum PDF informado (planta/memorial/quadro) para montar o pacote final.'
        )
    return ordem


def unir_pdfs(lista_paths, saida):
    """
    Une uma lista de PDFs (já na ordem final) em um único arquivo.

    Args:
        lista_paths: lista de caminhos de PDF, na ordem desejada (ver
            `montar_ordem_pdfs`).
        saida: caminho do PDF unificado de saída.

    Returns:
        os.PathLike: o próprio `saida`.

    Raises:
        RuntimeError: se ArcPy não estiver disponível neste ambiente.
        ValueError: se `lista_paths` estiver vazia.
    """
    if arcpy is None:
        raise RuntimeError('arcpy não disponível neste ambiente.')
    if not lista_paths:
        raise ValueError('Lista de PDFs vazia; nada para unir.')

    if len(lista_paths) == 1:
        if os.path.abspath(lista_paths[0]) != os.path.abspath(saida):
            import shutil
            shutil.copy2(lista_paths[0], saida)
        return saida

    if os.path.exists(saida):
        arcpy.Delete_management(saida)

    pdf_doc = arcpy.mp.PDFDocumentCreate(saida)
    for pdf_path in lista_paths:
        pdf_doc.appendPages(str(pdf_path))
    pdf_doc.saveAndClose()
    arcpy.AddMessage(f'PDF unificado com {len(lista_paths)} arquivo(s) de origem: {saida}')
    return saida


def exportar_pacote_final(planta, quadros, memoriais, saida, termo=None):
    """
    Monta a ordem final (Planta -> Quadro(s) -> Memorial(is) -> Termo) e
    une os PDFs parciais em `saida`.

    Args:
        planta: caminho do PDF da planta.
        quadros: caminho único ou lista de caminhos dos PDFs do Quadro de
            Confrontações; None quando não há folha adicional.
        memoriais: caminho único ou lista de caminhos dos PDFs do memorial.
        saida: caminho do PDF unificado final.
        termo: caminho do PDF do Termo de Autenticação.

    Returns:
        os.PathLike: o próprio `saida`.

    Raises:
        RuntimeError: se ArcPy não estiver disponível neste ambiente.
        ValueError: se nenhum PDF parcial for informado.
    """
    ordem = montar_ordem_pdfs(planta, quadros, memoriais, termo)
    return unir_pdfs(ordem, saida)
