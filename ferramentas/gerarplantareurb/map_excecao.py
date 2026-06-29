# -*- coding: utf-8 -*-

import os
import sys
import arcpy
import json

def map_excecao(mensagem, excecao, logger):
    json_erro = dict()

    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]

    arcpy.AddMessage(f'{mensagem}')
    logger.error(f'{mensagem}')
    arcpy.AddMessage(f'Type: {exc_type}')
    logger.error(f'Type: {exc_type}')
    arcpy.AddMessage(f'Filename: {fname}')
    logger.error(f'Filename: {fname}')
    arcpy.AddMessage(f'Line number: {exc_tb.tb_lineno}')
    logger.error(f'Line number: {exc_tb.tb_lineno}')

    json_erro[f'Função para fazer interseção entre camada do processos e camadas secundárias'] = str({f'Erro: {str(excecao)}', f'Type: {str(exc_type)}', f'Filename: {str(fname)}', f'Line number: {str(exc_tb.tb_lineno)}'})

    arcpy.AddMessage(json.dumps(json_erro))
    logger.error(excecao)

    # sys.exit()
    raise excecao