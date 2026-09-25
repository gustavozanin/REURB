# -*- coding: utf-8 -*-

"""Caminhos das camadas: modo SDE (geoserviço) ou FEATURESERVER (Desktop)."""

from glob import glob
from pathlib import Path
import os
import arcpy

# ============================================================================
# CONFIGURAÇÃO DE CONEXÃO DE BANCO DE DADOS (modo SDE)
# ============================================================================
CONEXAO_REGISTRADA_SERVIDOR = "gisdb"
USAR_CONEXAO_REGISTRADA = False

# ============================================================================
# MODO DE DADOS
# ============================================================================
# SDE: geoserviço / publicação no Server (comportamento original)
# FEATURESERVER: uso Desktop sem VPN (analistas no ArcGIS Pro)
MODO_DADOS = 'SDE'

FEATURESERVER_URL_PADRAO = (
    'https://www.arcgis.iterma.ma.gov.br/server/rest/services/'
    'CAMADAS_ITERMA/REURB_ITERMA/FeatureServer'
)

# IDs das camadas no FeatureServer REURB_ITERMA
FEATURESERVER_LAYERS = {
    'eixo_viario': 0,
    'confrontante_externo': 1,
    'bairro': 8,
    'lotes': 9,
    'quadras': 10,
}

CAMPOS_BAIRRO_ESPERADOS = (
    'n_coletivo',
    'status',
    'responsavel_tecnico',
    'nome',
)

# ============================================================================

nome_conexao_banco_dados = None
municipios_camada = None
bairro_camada = None
quadra_camada = None
lote_camada = None
eixo_viario_camada = None
confrontante_camada = None
responsavel_tecnico_tabela = None
fusos_utm_camada = None
_modo_atual = None
_featureserver_url_atual = None


def _pasta_databases():
    return Path(__file__).parent.joinpath('databases')


def _caminho_gdb_auxiliar():
    """GDB local com municipios e responsavel_tecnico (pacote Desktop)."""
    candidatos = [
        _pasta_databases() / 'auxiliar_desktop' / 'auxiliar_desktop.gdb',
        _pasta_databases() / 'auxiliar_desktop.gdb',
    ]
    for caminho in candidatos:
        if caminho.exists():
            return str(caminho).replace('\\', '/')
    return str(candidatos[0]).replace('\\', '/')


def obter_conexao_banco():
    """
    Obtém a conexão do banco de dados (modo SDE).

    Se USAR_CONEXAO_REGISTRADA = True, usa conexão registrada no servidor.
    Caso contrário, usa arquivo .sde local.
    """
    if USAR_CONEXAO_REGISTRADA:
        conexao_registrada = f"/enterpriseDatabases/{CONEXAO_REGISTRADA_SERVIDOR}"
        try:
            if arcpy.Exists(conexao_registrada):
                arcpy.AddMessage(f"Usando conexão registrada: {conexao_registrada}")
                try:
                    arcpy.ClearWorkspaceCache_management(conexao_registrada)
                except Exception as e:
                    arcpy.AddWarning(
                        f"Não foi possível limpar cache da conexão ({e}). Continuando."
                    )
                return conexao_registrada
            arcpy.AddWarning(
                f"Conexão registrada '{conexao_registrada}' não encontrada. "
                f"Tentando arquivo .sde local..."
            )
        except Exception as e:
            arcpy.AddWarning(
                f"Erro ao verificar conexão registrada: {str(e)}. "
                f"Tentando arquivo .sde local..."
            )

    databases_path = str(_pasta_databases())
    if os.path.exists(databases_path):
        arquivos_sde = glob(pathname=f'{databases_path}/*.sde')
        if arquivos_sde:
            arcpy.AddMessage(f"Usando arquivo .sde local: {arquivos_sde[0]}")
            try:
                arcpy.ClearWorkspaceCache_management(arquivos_sde[0])
            except Exception as e:
                arcpy.AddWarning(
                    f"Não foi possível limpar cache do .sde ({e}). Continuando."
                )
            return arquivos_sde[0]

    raise ValueError(
        f"Nenhuma conexão de banco de dados encontrada.\n"
        f"  - USAR_CONEXAO_REGISTRADA: {USAR_CONEXAO_REGISTRADA}\n"
        f"  - CONEXAO_REGISTRADA_SERVIDOR: {CONEXAO_REGISTRADA_SERVIDOR}\n"
        f"Coloque um arquivo .sde em '{databases_path}' ou use modo FEATURESERVER."
    )


def construir_caminho_feature(conexao_base, esquema, tabela):
    """Constrói caminho completo para feature class/tabela no banco SDE."""
    if conexao_base.startswith('/enterpriseDatabases'):
        if esquema:
            caminho1 = f"{conexao_base}/gisdb.sde.{esquema}/gisdb.sde.{tabela}"
            caminho2 = f"{conexao_base}/{esquema}.{tabela}"
            try:
                if arcpy.Exists(caminho1):
                    return caminho1
                if arcpy.Exists(caminho2):
                    return caminho2
            except Exception:
                pass
            return caminho1

        caminho1 = f"{conexao_base}/gisdb.sde.{tabela}"
        caminho2 = f"{conexao_base}/{tabela}"
        try:
            if arcpy.Exists(caminho1):
                return caminho1
            if arcpy.Exists(caminho2):
                return caminho2
        except Exception:
            pass
        return caminho1

    caminho_sde = str(conexao_base).replace('\\', '/')
    if esquema:
        return f"{caminho_sde}/gisdb.sde.{esquema}/gisdb.sde.{tabela}"
    return f"{caminho_sde}/gisdb.sde.{tabela}"


def _url_layer(featureserver_url, layer_id):
    base = featureserver_url.rstrip('/')
    return f'{base}/{layer_id}'


def reiniciar_caminhos():
    """Limpa o cache de caminhos para permitir reinicialização com outro modo."""
    global nome_conexao_banco_dados, municipios_camada, bairro_camada
    global quadra_camada, lote_camada, eixo_viario_camada, confrontante_camada
    global responsavel_tecnico_tabela, fusos_utm_camada
    global _modo_atual, _featureserver_url_atual

    nome_conexao_banco_dados = None
    municipios_camada = None
    bairro_camada = None
    quadra_camada = None
    lote_camada = None
    eixo_viario_camada = None
    confrontante_camada = None
    responsavel_tecnico_tabela = None
    fusos_utm_camada = None
    _modo_atual = None
    _featureserver_url_atual = None


def _inicializar_fusos():
    global fusos_utm_camada
    fusos_utm_camada = str(
        _pasta_databases().joinpath('fusos_utm', 'fusos_utm.shp')
    )


def _inicializar_auxiliar_desktop():
    """Municípios e responsável técnico a partir do GDB auxiliar."""
    global municipios_camada, responsavel_tecnico_tabela

    gdb = _caminho_gdb_auxiliar()
    municipios_camada = f'{gdb}/municipios'
    responsavel_tecnico_tabela = f'{gdb}/responsavel_tecnico'

    if not arcpy.Exists(municipios_camada):
        raise ValueError(
            f"Camada municipios não encontrada em '{gdb}'.\n"
            f"Peça ao TI para rodar o script de atualização do GDB auxiliar."
        )
    if not arcpy.Exists(responsavel_tecnico_tabela):
        raise ValueError(
            f"Tabela responsavel_tecnico não encontrada em '{gdb}'.\n"
            f"Peça ao TI para rodar o script de atualização do GDB auxiliar."
        )


def _inicializar_featureserver(featureserver_url):
    global nome_conexao_banco_dados, bairro_camada, quadra_camada
    global lote_camada, eixo_viario_camada, confrontante_camada

    url = (featureserver_url or FEATURESERVER_URL_PADRAO).rstrip('/')
    nome_conexao_banco_dados = url

    bairro_camada = _url_layer(url, FEATURESERVER_LAYERS['bairro'])
    quadra_camada = _url_layer(url, FEATURESERVER_LAYERS['quadras'])
    lote_camada = _url_layer(url, FEATURESERVER_LAYERS['lotes'])
    eixo_viario_camada = _url_layer(url, FEATURESERVER_LAYERS['eixo_viario'])
    confrontante_camada = _url_layer(
        url, FEATURESERVER_LAYERS['confrontante_externo']
    )

    arcpy.AddMessage(f"Modo FEATURESERVER: {url}")
    arcpy.AddMessage(f"Bairro: {bairro_camada}")
    _inicializar_auxiliar_desktop()


def _inicializar_sde():
    global nome_conexao_banco_dados, municipios_camada, bairro_camada
    global quadra_camada, lote_camada, eixo_viario_camada, confrontante_camada
    global responsavel_tecnico_tabela

    nome_conexao_banco_dados = obter_conexao_banco()
    municipios_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'bases', 'municipios'
    )
    bairro_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'edicao', 'bairro'
    )
    quadra_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'edicao', 'quadras'
    )
    lote_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'edicao', 'lotes'
    )
    eixo_viario_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'edicao', 'eixo_viario'
    )
    confrontante_camada = construir_caminho_feature(
        nome_conexao_banco_dados, 'edicao', 'confrontante_externo'
    )
    responsavel_tecnico_tabela = construir_caminho_feature(
        nome_conexao_banco_dados, None, 'responsavel_tecnico'
    )
    arcpy.AddMessage("Modo SDE inicializado")


def inicializar_caminhos(modo=None, featureserver_url=None, forcar=False):
    """
    Inicializa todos os caminhos.

    Args:
        modo: 'SDE' ou 'FEATURESERVER'. Se None, usa MODO_DADOS.
        featureserver_url: URL base do FeatureServer (modo FEATURESERVER).
        forcar: se True, reinicia mesmo já inicializado.
    """
    global _modo_atual, _featureserver_url_atual

    modo_desejado = (modo or MODO_DADOS or 'SDE').upper()
    url_desejada = featureserver_url or FEATURESERVER_URL_PADRAO

    if not forcar and nome_conexao_banco_dados is not None:
        if _modo_atual == modo_desejado and (
            modo_desejado != 'FEATURESERVER'
            or _featureserver_url_atual == url_desejada.rstrip('/')
        ):
            return

    if forcar or nome_conexao_banco_dados is not None:
        reiniciar_caminhos()

    try:
        _inicializar_fusos()
        if modo_desejado == 'FEATURESERVER':
            _inicializar_featureserver(url_desejada)
        else:
            _inicializar_sde()
        _modo_atual = modo_desejado
        _featureserver_url_atual = (
            url_desejada.rstrip('/') if modo_desejado == 'FEATURESERVER' else None
        )
    except Exception as e:
        arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
        raise


dict_camadas = {
    'bairro_camada': bairro_camada
}
