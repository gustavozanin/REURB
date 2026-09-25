# -*- coding: utf-8 -*-

import logging
from glob import glob
from os import remove
from os.path import join, exists
from datetime import datetime

def logger_process(
        name: str,
        output: str
    ):
    """
    Responsável por montar o log de processamento.

    -------
    Parameters:
        name(str):
            Nome do arquivo que será gravado as etapas.
        output(str):
            Caminho para o diretório em que será salvo o arquivo de log.

    -------
    Returns:
        Logger:
            Objeto responsável pela configuração do log.
    """
    files_log = glob(
        pathname=join(
            output,
            name.split('.')[-1] +'*.log')
    )
    name_file = name.split('.')[-1] + datetime.now().strftime("_%d_%m_%Y_%H_%M_%S") + '.log'
    for file in files_log:
        present = datetime.now()
        log_date_temp = file.split('_')
        log_date = datetime(year=int(log_date_temp[-4]), month=int(log_date_temp[-5]), day=int(log_date_temp[-6]))
        if (present-log_date).days > 10:
            remove(path=file)
        elif join(output, name_file) == file:
            remove(file)    
    handler = logging.FileHandler(
        join(output, name_file)
    )
    handler.setFormatter(
        logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%d/%m/%Y %H:%M:%S'
        )
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    return logger
    
def logger_error(
        logger: logging,
        messages: str
    ):
    """
    """
    dict_arcmessage_code = {
        0: 'Informative message',
        1: 'Definition message',
        2: 'Start message',
        3: 'Stop message',
        50: 'Warning message',
        100: 'Error message',
        101: 'Empty message',
        102: 'Geodatabase error message',
        200: 'Abort message'
    }
    for message in messages:
        message[0] = (dict_arcmessage_code[message[0]])
        logger.error(message)
    logger.exception(messages[3][2])