# -*- coding: utf-8 -*-

"""Copia PDF e ZIP gerados para a pasta escolhida pelo analista."""

import json
import os
import shutil
import arcpy


def _copiar_sem_sobrescrever(origem, destino):
    if os.path.exists(destino):
        raise ValueError(
            'Já existe um arquivo neste caminho e a ferramenta não '
            'sobrescreve: {}'.format(destino)
        )
    pasta = os.path.dirname(destino)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    shutil.copy2(origem, destino)


def salvar_artefatos_desktop(
    pasta_saida: os.PathLike,
    numero_reurb_coletivo: str,
    pdf_planta: os.PathLike,
    zip_lote: os.PathLike,
    prefixo: str = 'planta_loteamento',
) -> dict:
    """
    Copia PDF e ZIP para pasta_saida e devolve caminhos finais.
    """
    if not pasta_saida:
        raise ValueError('Pasta de saída não informada')

    os.makedirs(pasta_saida, exist_ok=True)
    slug = numero_reurb_coletivo.replace('/', '_')
    pdf_destino = os.path.join(pasta_saida, f'{prefixo}_{slug}.pdf')
    zip_destino = os.path.join(pasta_saida, f'shape_{slug}.zip')

    _copiar_sem_sobrescrever(pdf_planta, pdf_destino)
    _copiar_sem_sobrescrever(zip_lote, zip_destino)

    arcpy.AddMessage(f'PDF salvo em: {pdf_destino}')
    arcpy.AddMessage(f'Shapefile ZIP salvo em: {zip_destino}')

    return {
        'pdf': pdf_destino,
        'zip': zip_destino,
        'numeroProcessoColetivo': numero_reurb_coletivo,
    }


def json_resumo_desktop(artefatos: dict, pronto: bool = True) -> str:
    """JSON curto para o parâmetro de saída da ferramenta Desktop."""
    payload = {
        'pronto': pronto,
        'pdf': artefatos.get('pdf', ''),
        'zip': artefatos.get('zip', ''),
        'numeroProcessoColetivo': artefatos.get('numeroProcessoColetivo', ''),
        'mensagem': (
            'Geração concluída. Abra o PDF e o ZIP na pasta de saída.'
            if pronto
            else 'Geração não concluída. Veja as mensagens da ferramenta.'
        ),
    }
    return json.dumps(payload, ensure_ascii=False)
