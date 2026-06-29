# -*- coding: utf-8 -*-

from glob import glob
from pathlib import Path
import os
from types import NoneType
import arcpy

# ============================================================================
# CONFIGURAÇÃO DE CONEXÃO DE BANCO DE DADOS
# ============================================================================
# Para usar conexão registrada no ArcGIS Server:
#   1. Configure CONEXAO_REGISTRADA_SERVIDOR com o nome da conexão registrada
#   2. Configure USAR_CONEXAO_REGISTRADA = True
#
# Para usar arquivo .sde local (desenvolvimento):
#   1. Configure USAR_CONEXAO_REGISTRADA = False
#   2. Coloque o arquivo .sde no diretório 'databases/'
# ============================================================================

# Nome da conexão registrada no ArcGIS Server
# Exemplo: se você registrou como "gisdb_sde" no servidor, use "gisdb_sde"
CONEXAO_REGISTRADA_SERVIDOR = "GIS_BD_Ramificacao"  # ALTERE AQUI com o nome da sua conexão

# Indica se deve usar conexão registrada (True) ou arquivo .sde local (False)
USAR_CONEXAO_REGISTRADA = False  # Altere para True quando publicar no servidor

# ============================================================================


def obter_conexao_banco():
    """
    Obtém a conexão do banco de dados.
    
    Se USAR_CONEXAO_REGISTRADA = True, usa conexão registrada no servidor.
    Caso contrário, usa arquivo .sde local (fallback para desenvolvimento).
    
    Returns:
        str: Caminho da conexão de banco de dados
    """
    if USAR_CONEXAO_REGISTRADA:
        # Usar conexão registrada no ArcGIS Server
        conexao_registrada = f"/enterpriseDatabases/{CONEXAO_REGISTRADA_SERVIDOR}"
        try:
            if arcpy.Exists(conexao_registrada):
                arcpy.AddMessage(f"✓ Usando conexão registrada: {conexao_registrada}")
                return conexao_registrada
            else:
                arcpy.AddWarning(
                    f"⚠ Conexão registrada '{conexao_registrada}' não encontrada.\n"
                    f"  Verifique se a conexão '{CONEXAO_REGISTRADA_SERVIDOR}' está registrada no ArcGIS Server.\n"
                    f"  Tentando usar arquivo .sde local como fallback..."
                )
                # Continua para tentar arquivo .sde como fallback
        except Exception as e:
            arcpy.AddWarning(
                f"⚠ Erro ao verificar conexão registrada: {str(e)}\n"
                f"  Tentando usar arquivo .sde local como fallback..."
            )
            # Continua para tentar arquivo .sde como fallback
    
    # Usar arquivo .sde local (desenvolvimento ou fallback)
    databases_path = str(
        Path(__file__).
            parent.
                joinpath('databases')
    )
    
    if os.path.exists(databases_path):
        arquivos_sde = glob(pathname=f'{databases_path}/*.sde')
        if arquivos_sde:
            arcpy.AddMessage(f"✓ Usando arquivo .sde local: {arquivos_sde[0]}")
            return arquivos_sde[0]
    
    raise ValueError(
        f"Nenhuma conexão de banco de dados encontrada.\n"
        f"Configuração atual:\n"
        f"  - USAR_CONEXAO_REGISTRADA: {USAR_CONEXAO_REGISTRADA}\n"
        f"  - CONEXAO_REGISTRADA_SERVIDOR: {CONEXAO_REGISTRADA_SERVIDOR}\n\n"
        f"Verifique:\n"
        f"  1. Se USAR_CONEXAO_REGISTRADA = True, certifique-se de que a conexão '{CONEXAO_REGISTRADA_SERVIDOR}' está registrada no ArcGIS Server\n"
        f"  2. Se USAR_CONEXAO_REGISTRADA = False, coloque um arquivo .sde no diretório '{databases_path}'"
    )


def construir_caminho_feature(conexao_base, esquema, tabela):
    """
    Constrói caminho completo para feature class/tabela no banco.
    Mantém compatibilidade com o formato atual: gisdb.sde.esquema.tabela
    
    Args:
        conexao_base: Caminho da conexão (arquivo .sde ou conexão registrada)
        esquema: Nome do esquema (ex: 'bases', 'edicao') ou None se não houver esquema
        tabela: Nome da tabela/feature class
    
    Returns:
        str: Caminho completo da feature class
    """
    # Se for conexão registrada (começa com /enterpriseDatabases)
    if conexao_base.startswith('/enterpriseDatabases'):
        # Para conexões registradas, o formato pode variar
        if esquema:
            # Tenta primeiro o formato: /enterpriseDatabases/nome/gisdb.sde.esquema/gisdb.sde.tabela
            caminho1 = f"{conexao_base}/gisdb.sde.{esquema}/gisdb.sde.{tabela}"
            # Tenta também: /enterpriseDatabases/nome/esquema.tabela
            caminho2 = f"{conexao_base}/{esquema}.{tabela}"
            
            # Verifica qual formato funciona
            try:
                if arcpy.Exists(caminho1):
                    return caminho1
                elif arcpy.Exists(caminho2):
                    return caminho2
                else:
                    # Retorna o formato padrão (será testado quando usado)
                    return caminho1
            except:
                # Se não conseguir verificar, retorna o formato padrão
                return caminho1
        else:
            # Sem esquema: /enterpriseDatabases/nome/gisdb.sde.tabela
            caminho1 = f"{conexao_base}/gisdb.sde.{tabela}"
            caminho2 = f"{conexao_base}/{tabela}"
            
            try:
                if arcpy.Exists(caminho1):
                    return caminho1
                elif arcpy.Exists(caminho2):
                    return caminho2
                else:
                    return caminho1
            except:
                return caminho1
    else:
        # Formato para arquivo .sde local
        # IMPORTANTE: ArcGIS usa '/' como separador após o arquivo .sde, não o separador do sistema
        caminho_sde = str(conexao_base).replace('\\', '/')  # Normaliza separadores
        
        if esquema:
            # Com esquema: arquivo.sde/gisdb.sde.esquema/gisdb.sde.tabela
            return f"{caminho_sde}/gisdb.sde.{esquema}/gisdb.sde.{tabela}"
        else:
            # Sem esquema: arquivo.sde/gisdb.sde.tabela
            return f"{caminho_sde}/gisdb.sde.{tabela}"

# No final de caminho_camadas.py, substitua as linhas 147-216 por:

# Variáveis globais (serão inicializadas quando necessário)
nome_conexao_banco_dados = None
lote_camada = None
quadra_camada = None
bairro_camada = None

def inicializar_caminhos():
    """Inicializa todos os caminhos. Deve ser chamada antes de usar as variáveis."""
    global nome_conexao_banco_dados, bairro_camada, lote_camada, quadra_camada
    
    if nome_conexao_banco_dados is not None:
        return  # Já foi inicializado
    
    try:
        nome_conexao_banco_dados = obter_conexao_banco()
    
        bairro_camada = construir_caminho_feature(nome_conexao_banco_dados, 'edicao', 'bairro')
        lote_camada = construir_caminho_feature(nome_conexao_banco_dados, 'edicao', 'lotes')
        quadra_camada = construir_caminho_feature(nome_conexao_banco_dados, 'edicao', 'quadras')
    except Exception as e:
        import arcpy
        arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
        raise

# Inicializa na importação, mas com tratamento de erro
try:
    inicializar_caminhos()
except:
    pass  # Falha silenciosa na importação, será inicializado depois

dict_camadas = {
    'bairro_camada': bairro_camada,
    'lote_camada': lote_camada,
    'quadra_camada': quadra_camada
}

def validar_conexao_banco():
    """Valida se a conexão do banco está acessível."""
    inicializar_caminhos()  # Garante que está inicializado
    
    try:
        desc = arcpy.Describe(bairro_camada)
        arcpy.AddMessage(f"✓ Validação de conexão bem-sucedida")
        return True
    except Exception as e:
        arcpy.AddWarning(f"⚠ Aviso ao validar conexão: {str(e)}")
        return False
