# -*- coding: utf-8 -*-

import configparser
import os
import unicodedata


ARQUIVO_RESPONSAVEIS = os.path.join(os.path.dirname(__file__), 'responsaveis_tecnicos.txt')
RESPONSAVEL_PADRAO_CAMPO_DE_POUSO = 'bruna_silva_sa_pereira'


def normalizar_id(texto):
    texto = unicodedata.normalize('NFKD', str(texto or ''))
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    texto = texto.lower().strip()
    for char in [' ', '-', '.', ',', 'º', 'ª', ':', '/', '\\']:
        texto = texto.replace(char, '_')
    while '__' in texto:
        texto = texto.replace('__', '_')
    return texto.strip('_')


def carregar_responsaveis():
    parser = configparser.ConfigParser()
    parser.optionxform = str
    parser.read(ARQUIVO_RESPONSAVEIS, encoding='utf-8')

    responsaveis = {}
    for secao in parser.sections():
        dados = dict(parser[secao])
        responsaveis[secao] = {
            'id': secao,
            'nome': dados.get('nome', ''),
            'email': dados.get('email', ''),
            'formacao': dados.get('formacao', ''),
            'registro': dados.get('registro', ''),
        }
        responsaveis[normalizar_id(dados.get('nome', secao))] = responsaveis[secao]
    return responsaveis


def resolver_responsavel(json_entrada):
    responsaveis = carregar_responsaveis()
    valor = json_entrada.get('responsavelTecnico', '')

    if isinstance(valor, dict):
        chave = valor.get('id') or valor.get('nome') or valor.get('responsavelTecnico') or ''
    else:
        chave = valor

    dados = json_entrada.get('dados', {})
    bairro = normalizar_id(dados.get('bairro', ''))
    numero = str(dados.get('numeroProcessoColetivo', ''))

    if not chave and ('campo_de_pouso' in bairro or numero == '051201571/2026'):
        chave = RESPONSAVEL_PADRAO_CAMPO_DE_POUSO

    chave_normalizada = normalizar_id(chave)
    responsavel = responsaveis.get(chave) or responsaveis.get(chave_normalizada)

    if responsavel:
        return responsavel

    return {
        'id': '',
        'nome': '',
        'email': '',
        'formacao': '',
        'registro': '',
    }
