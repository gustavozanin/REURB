# -*- coding: utf-8 -*-

from glob import glob
from pathlib import Path
import os
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
CONEXAO_REGISTRADA_SERVIDOR = "gisdb"  # ALTERE AQUI com o nome da sua conexão

# Indica se deve usar conexão registrada (True) ou arquivo .sde local (False)
USAR_CONEXAO_REGISTRADA = True # Altere para True quando publicar no servidor

# ============================================================================

def limpar_cache_workspace(caminho_conexao):
    """Limpa o cache da conexão quando possível, sem bloquear a execução."""
    try:
        arcpy.ClearWorkspaceCache_management(caminho_conexao)
        arcpy.AddMessage(f"✓ Conexão do banco de dados atualizada")
    except Exception as e:
        arcpy.AddWarning(
            f"⚠ Não foi possível limpar o cache da conexão '{caminho_conexao}'. "
            f"A execução continuará usando a conexão existente. Detalhe: {str(e)}"
        )

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
                limpar_cache_workspace(conexao_registrada)
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
    databases_path_local = Path(__file__).parent.joinpath('databases')
    databases_path_pacote = Path(arcpy.env.packageWorkspace).parent.joinpath('cd', 'databases')
    databases_path = str(databases_path_local if databases_path_local.exists() else databases_path_pacote)
    
    if os.path.exists(databases_path):
        arquivos_sde = glob(pathname=f'{databases_path}/*.sde')
        if arquivos_sde:
            arcpy.AddMessage(f"✓ Usando arquivo .sde local: {arquivos_sde[0]}")
            limpar_cache_workspace(arquivos_sde[0])
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
municipios_camada = None
bairro_camada = None
responsavel_tecnico_tabela = None
fusos_utm_camada = None
BAIRRO_CAMADA_LOCAL = r"C:\REURB\SHP\bairro_camada.shp"
BAIRROS_SHP_DIR = Path(r"C:\REURB\SHP")
FEATURESERVER_REURB_ITERMA = "https://www.arcgis.iterma.ma.gov.br/server/rest/services/CAMADAS_ITERMA/REURB_ITERMA/FeatureServer"
BAIRRO_FEATURE_SERVICE = f"{FEATURESERVER_REURB_ITERMA}/8"
PREFERIR_FEATURESERVER = True
MUNICIPIOS_GDB_LOCAL = Path(__file__).parent.joinpath('databases', 'municipios_grid_utm.gdb')

def obter_municipios_local():
    """Localiza a feature class de municípios na geodatabase local."""
    if not MUNICIPIOS_GDB_LOCAL.exists():
        return None

    try:
        for dirpath, dirnames, filenames in arcpy.da.Walk(
            str(MUNICIPIOS_GDB_LOCAL),
            datatype='FeatureClass',
            type='Polygon'
        ):
            for filename in filenames:
                feature = os.path.join(dirpath, filename)
                campos = {field.name.upper() for field in arcpy.ListFields(feature)}
                if {'CD_MUN', 'NM_MUN'}.issubset(campos) or {'GEOCODIGO', 'NOME'}.issubset(campos):
                    arcpy.AddMessage(f"✓ Usando municipios local: {feature}")
                    return feature
    except Exception as e:
        arcpy.AddWarning(f"⚠ Não foi possível localizar municípios local: {str(e)}")

    return None

def obter_bairro_feature_service(numero_reurb_coletivo=None):
    """Localiza o bairro na camada publicada do FeatureServer pelo n_coletivo."""
    if not numero_reurb_coletivo:
        return None

    valores = {
        numero_reurb_coletivo,
        numero_reurb_coletivo.replace('_', '/'),
        numero_reurb_coletivo.replace('/', '_')
    }

    try:
        if not arcpy.Exists(BAIRRO_FEATURE_SERVICE):
            arcpy.AddWarning(f"FeatureServer de bairros nao acessivel: {BAIRRO_FEATURE_SERVICE}")
            return None

        campos = {field.name for field in arcpy.ListFields(BAIRRO_FEATURE_SERVICE)}
        if 'n_coletivo' not in campos:
            arcpy.AddWarning("Campo n_coletivo nao encontrado no FeatureServer de bairros.")
            return None

        where = " OR ".join([f"n_coletivo = '{valor}'" for valor in valores])
        with arcpy.da.SearchCursor(BAIRRO_FEATURE_SERVICE, ['n_coletivo'], where) as cursor:
            for _ in cursor:
                arcpy.AddMessage(f"✓ Usando bairro do FeatureServer: {BAIRRO_FEATURE_SERVICE}")
                return BAIRRO_FEATURE_SERVICE
    except Exception as e:
        arcpy.AddWarning(f"Não foi possível consultar o FeatureServer de bairros: {str(e)}")

    return None

def obter_bairro_local(numero_reurb_coletivo=None):
    """Localiza um shapefile local de bairro pelo n_coletivo, com fallback legado."""
    candidatos = []
    if BAIRROS_SHP_DIR.exists():
        candidatos.extend(BAIRROS_SHP_DIR.glob("bairro*.shp"))

    if numero_reurb_coletivo:
        valores = {
            numero_reurb_coletivo,
            numero_reurb_coletivo.replace('_', '/'),
            numero_reurb_coletivo.replace('/', '_')
        }
        encontrados = []
        for candidato in candidatos:
            try:
                campos = {field.name for field in arcpy.ListFields(str(candidato))}
                if 'n_coletivo' not in campos:
                    continue
                where = " OR ".join([f"n_coletivo = '{valor}'" for valor in valores])
                with arcpy.da.SearchCursor(str(candidato), ['n_coletivo'], where) as cursor:
                    for _ in cursor:
                        encontrados.append(candidato)
                        break
            except Exception as e:
                arcpy.AddWarning(f"⚠ Não foi possível verificar bairro local {candidato}: {str(e)}")

        if encontrados:
            numero_nome = numero_reurb_coletivo.replace('/', '_').replace('-', '_')
            encontrados = sorted(
                encontrados,
                key=lambda path: (
                    numero_nome.lower() in path.stem.lower(),
                    os.path.getmtime(str(path))
                ),
                reverse=True
            )
            escolhido = encontrados[0]
            arcpy.AddMessage(f"✓ Usando bairro_camada local: {escolhido}")
            return str(escolhido)

    if os.path.exists(BAIRRO_CAMADA_LOCAL):
        arcpy.AddMessage(f"✓ Usando bairro_camada local: {BAIRRO_CAMADA_LOCAL}")
        return BAIRRO_CAMADA_LOCAL

    return None

def inicializar_caminhos(numero_reurb_coletivo=None):
    """Inicializa todos os caminhos. Deve ser chamada antes de usar as variáveis."""
    global nome_conexao_banco_dados, municipios_camada, bairro_camada, responsavel_tecnico_tabela, fusos_utm_camada
    
    if nome_conexao_banco_dados is not None:
        bairro_servico = obter_bairro_feature_service(numero_reurb_coletivo) if PREFERIR_FEATURESERVER else None
        bairro_local = obter_bairro_local(numero_reurb_coletivo)
        bairro_camada = bairro_servico or bairro_local or bairro_camada
        if 'atualizar_dict_camadas' in globals():
            atualizar_dict_camadas()
        return  # Já foi inicializado
    
    try:
        fusos_utm_local = Path(__file__).parent.joinpath('databases', 'fusos_utm', 'fusos_utm.shp')
        if fusos_utm_local.exists():
            fusos_utm_camada = str(fusos_utm_local)
        else:
            fusos_utm_camada = str(
                Path(__file__).
                    parents[2].
                        joinpath('cd', 'databases', 'fusos_utm', 'fusos_utm.shp')
            )

        municipios_camada = obter_municipios_local()
        
        bairro_servico = obter_bairro_feature_service(numero_reurb_coletivo) if PREFERIR_FEATURESERVER else None
        bairro_local = obter_bairro_local(numero_reurb_coletivo)
        bairro_camada = bairro_servico or bairro_local

        if bairro_camada is None or municipios_camada is None:
            nome_conexao_banco_dados = obter_conexao_banco()

        if municipios_camada is None:
            municipios_camada = construir_caminho_feature(nome_conexao_banco_dados, 'bases', 'municipios')
        if bairro_camada is None:
            bairro_camada = construir_caminho_feature(nome_conexao_banco_dados, 'edicao', 'bairro')

        if nome_conexao_banco_dados is not None:
            responsavel_tecnico_tabela = construir_caminho_feature(nome_conexao_banco_dados, None, 'responsavel_tecnico')
        if 'atualizar_dict_camadas' in globals():
            atualizar_dict_camadas()
    except Exception as e:
        arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
        raise

# Inicializa na importação, mas com tratamento de erro
try:
    inicializar_caminhos()
except:
    pass  # Falha silenciosa na importação, será inicializado depois

dict_camadas = {}

def atualizar_dict_camadas():
    dict_camadas['bairro_camada'] = bairro_camada

atualizar_dict_camadas()

def validar_conexao_banco():
    """Valida se a conexão do banco está acessível."""
    inicializar_caminhos()  # Garante que está inicializado
    
    try:
        desc = arcpy.Describe(municipios_camada)
        arcpy.AddMessage(f"✓ Validação de conexão bem-sucedida")
        return True
    except Exception as e:
        arcpy.AddWarning(f"⚠ Aviso ao validar conexão: {str(e)}")
        return False
