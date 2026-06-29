# -*- coding: utf-8 -*-

import os
import json
import arcpy
from pathlib import Path
from glob import glob 
from datetime import datetime

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Gerar Planta REURB"
        self.alias = "GerarPlantaREURB"

        # List of tool classes associated with this toolbox
        self.tools = []
        self.tools.append(GerarPlantaREURBTool)

class GerarPlantaREURBTool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "GerarPlantaREURBTool"
        self.description = "Ferramenta realiza geração de planta de lote de REURB."
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Define the tool parameters."""
        feature_input = arcpy.Parameter(
            name='inputJson',
            displayName='inputJson',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        info_saida = arcpy.Parameter(
            name='outputJson',
            displayName='outputJson',
            direction='Output',
            datatype='GPString',
            parameterType='Derived'
        )
        params = []
        params.append(feature_input)
        params.append(info_saida)
        return params

    def isLicensed(self):
        """Set whether the tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        try:
            from caminho_camadas import (
                inicializar_caminhos,
                quadra_camada,
                lote_camada,
                responsavel_tecnico_tabela,
                municipios_camada,
                eixo_viario_camada
            )
            from tabela_modelo import (
                json_saida_modelo,
                json_dados_perimetro_modelo
            )
            from check_reurb_coletivo import check_reurb_coletivo
            from check_lote import check_lote
            from check_responsavel import check_responsavel_tecnico
            from exporta_shapefile import exporta_shapefile, zipar_shapefile
            from municipalidade import municipalidade
            from transforma_lote import transforma_lote
            from azminute import azimute
            from confrontantes import confrontantes
            from formatar_tabela_atributos import formatar_tabela_atributos
            from exporta_camadas_para_layout import exporta_camadas_para_layout
            from gerar_planta import gerar_planta, exportar_planta_para_pdf
            from formatar_json_saida import formatar_json_saida
            from formatar_dados_perimetro import formatar_dados_perimetro
            from transforma_vertices_em_linhas import transforma_vertices_em_linhas
        except ImportError as e:
            arcpy.AddError(f"Erro ao importar módulos: {str(e)}")
            raise

        # Inicializar caminhos
        try:
            from caminho_camadas import inicializar_caminhos
            inicializar_caminhos()
        except Exception as e:
            arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
            raise

        # Atualizar conexão do banco de dados
        arcpy.AddMessage('Início - Atualizando conexão com o banco de dados.')
        try:
            databases_path = str(Path(__file__).parent.joinpath('databases'))
            
            if os.path.exists(databases_path):
                arquivo_sde = glob(pathname=f'{databases_path}/*.sde')[0]

            arcpy.ClearWorkspaceCache_management(arquivo_sde)

        except Exception as e:
            arcpy.AddMessage(f'Não foi possível atualizar a conexão com o banco de dados: {str(e)}')
        arcpy.AddMessage('Fim - Conexão com o banco de dados atualizada.')

        # Verificar se as variáveis foram inicializadas
        if lote_camada is None or quadra_camada is None:
            arcpy.AddError("Erro: Caminhos não foram inicializados corretamente")
            raise ValueError("Caminhos não inicializados")
            
        # logger = logger_process(
        #     name='Bloqueio_Dinamico',
        #     output=output_log
        # )
        try:
            # if arcpy.Exists(arcpy.env.scratchGDB):
            #     arcpy.Delete_management(arcpy.env.scratchGDB)

            scrachgdb = arcpy.env.scratchGDB

            arcpy.AddMessage('Início - Executando comando para obter parâmetros e referencias espaciais')
            json_entrada = json.loads(parameters[0].valueAsText.replace("'", "")) #
            
            interessado_cpf = json_entrada['identificacaoPlanilha']['cpfCnpj']
            interessado = json_entrada['identificacaoPlanilha']['nome']
            lote = json_entrada['identificacaoPlanilha']['lote']
            quadra = int(json_entrada['identificacaoPlanilha']['quadra'])
            # endereco = json_entrada['identificacaoPlanilha']['endereco']
            # bairro = json_entrada['identificacaoPlanilha']['bairro']
            # responsavel_tecnico = json_entrada['responsavelTecnico']['nome']
            # formacao = json_entrada['responsavelTecnico']['formacao']
            # codigo_credenciamento = json_entrada['responsavelTecnico']['codigoCredenciamento']
            numero_reurb_coletivo = json_entrada['numeroProcessoColetivo']
            arcpy.AddMessage('Fim - Executando comando para obter parâmetros e referencias espaciais')

            json_saida = json_saida_modelo
            json_dados_perimetro = json_dados_perimetro_modelo

            with arcpy.EnvManager(workspace=scrachgdb, overwriteOutput=True):

                #verificar se o número do REURB coletivo existe
                arcpy.AddMessage('Início - Verificando se o número do REURB coletivo existe')
                reurb_coletivo_existe = check_reurb_coletivo(
                    lote_features=lote_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo
                )

                if reurb_coletivo_existe is False:
                    json_saida['pronto'] = False
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                arcpy.AddMessage('Fim - Verificando se o número do REURB coletivo existe')

                #verificar se o lote existe
                arcpy.AddMessage('Início - Verificando se o lote existe')
                pronto = check_lote(
                    lote_features=lote_camada,
                    quadra_features=quadra_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    quadra=quadra,
                    lote=lote
                )

                if pronto is False:
                    json_saida['pronto'] = pronto
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                arcpy.AddMessage('Fim - Verificando se o lote existe')

                #verificar se o responsável técnico existe
                arcpy.AddMessage('Início - Verificando se o responsável técnico existe')
                responsavel_tecnico_existe, responsavel_tecnico, formacao, codigo_credenciamento = check_responsavel_tecnico(
                    lote_features=lote_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    quadra=quadra,
                    lote=lote,
                    responsavel_tecnico_tabela=responsavel_tecnico_tabela
                )

                if responsavel_tecnico_existe is False:
                    arcpy.AddMessage(f'Responsável técnico {responsavel_tecnico} não cadastrado ou preenchimento incorreto')
                    json_saida['pronto'] = False
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                arcpy.AddMessage('Fim - Verificando se o responsável técnico existe')

                #exportar lote para shapefile, zipar, encontrar fuso utm, calcula area e perimetro
                arcpy.AddMessage('Início - Exportando lote para shapefile, zipando, encontrando endereço, bairro, fuso utm e banda utm, calculando area e perimetro')
                dir_shapefile, lote_selecionado, codigo_fuso_lote, banda_utm, meridiano_central, area_lote, perimetro_lote, n_predial, rua, bairro = exporta_shapefile(
                    lote_features=lote_camada,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    quadra=quadra,
                    lote=lote
                )
                arcpy.AddMessage('Fim - Exportando lote para shapefile, zipando, encontrando endereço, bairro, fuso utm e banda utm, calculando area e perimetro')

                #verificar se o endereço e bairro do lote existem
                arcpy.AddMessage('Início - Verificando se o endereço e bairro do lote estão preenchidos')
                if rua is None or bairro is None or rua == '' or bairro == '':
                    arcpy.AddError('Endereço ou bairro do lote não estão preenchidos')
                    json_saida['pronto'] = False
                    result_json = json.dumps(json_saida, ensure_ascii=False)
                    arcpy.SetParameter(1, result_json)
                    return result_json
                arcpy.AddMessage('Fim - Verificando se o endereço e bairro do lote estão preenchidos')
                
                #selecionar municipio de acordo com o lote
                arcpy.AddMessage('Início - Selecionando municipio de acordo com o lote')
                municipio, municipio_principal = municipalidade(
                    feicao_propriedade=lote_selecionado,
                    municipios=municipios_camada,
                    area=area_lote
                )
                arcpy.AddMessage('Fim - Selecionando municipio de acordo com o lote')

                #transformar lote em linha e vertices em pontos
                arcpy.AddMessage('Início - Transformando lote em linha e vertices em pontos')
                divisas_lote, vertices_lote = transforma_lote(
                    lote_selecionado=lote_selecionado
                )
                arcpy.AddMessage('Fim - Transformando lote em linha e vertices em pontos')

                #calcular azimute e distancia de cada vertice
                arcpy.AddMessage('Início - Calculando azimute e distancia de cada vertice')
                azimute(
                    in_features=vertices_lote
                )
                arcpy.AddMessage('Fim - Calculando azimute e distancia de cada vertice')

                #transforma vertices em linhas
                arcpy.AddMessage('Início - Transformando vertices em linhas')
                confrontantes_lote = transforma_vertices_em_linhas(
                    vertices_lote=vertices_lote
                )                
                arcpy.AddMessage('Fim - Transformando vertices em linhas')

                #encontrar confrontantes
                arcpy.AddMessage('Início - Encontrando confrontantes')
                confrontantes(
                    in_feature=confrontantes_lote,
                    lote=lote,
                    lote_features=lote_camada,
                    eixo_viario=eixo_viario_camada
                )
                arcpy.AddMessage('Fim - Encontrando confrontantes')

                #formatar tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N
                arcpy.AddMessage('Início - Formatando tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N')
                confrontantes_lote_final = formatar_tabela_atributos(
                    in_features=confrontantes_lote
                )
                arcpy.AddMessage('Fim - Formatando tabela de atributos com as informações: de(vértice), para(vértice), azimute, distancia, coordenadas E e N')

                #exportar camadas para o layout
                lotes_layout, eixo_viario_layout = exporta_camadas_para_layout(
                    confrontantes_lote=confrontantes_lote_final,
                    n_reurb_coletivo=numero_reurb_coletivo,
                    n_quadra=quadra,
                    lote=lote_camada,
                    eixo_viario=eixo_viario_camada
                )
                arcpy.AddMessage('Fim - Exportando camadas para o layout')

                #gerar planta
                arcpy.AddMessage('Início - Gerando planta')
                layout_planta = gerar_planta(
                    lote_selecionado=lote_selecionado,
                    confrontantes_lote=confrontantes_lote_final,
                    vertices_lote=vertices_lote,
                    lotes_layout=lotes_layout,
                    interessado=interessado,
                    interessado_cpf=interessado_cpf,
                    bairro=bairro,
                    municipio=municipio_principal['nome'],
                    logradouro=rua,
                    quadra=quadra,
                    lote=lote,
                    area=area_lote,
                    perimetro=perimetro_lote,
                    data=datetime.now().strftime('%d/%m/%Y'),
                    fusoutm=codigo_fuso_lote,
                    banda=banda_utm,
                    responsavel_tecnico=responsavel_tecnico,
                    funcao=formacao,
                    n_crea_cau=codigo_credenciamento
                )
                arcpy.AddMessage('Fim - Gerando planta')

                arcpy.AddMessage('Início - Zipando shapefile')
                zip_lote = zipar_shapefile(
                    dir_shapefile=dir_shapefile
                )
                arcpy.AddMessage('Fim - Zipando shapefile')

                #exportar planta para PDF
                arcpy.AddMessage('Início - Exportando planta para PDF')
                pdf_planta = exportar_planta_para_pdf(
                    layout_planta=layout_planta,
                    numero_reurb_coletivo=numero_reurb_coletivo,
                    quadra=quadra,
                    lote=lote
                )
                arcpy.AddMessage('Fim - Exportando planta para PDF')

                #formatar dados perimetro
                arcpy.AddMessage('Início - Formatando dados perimetro')
                dados_perimetro = formatar_dados_perimetro(
                    confrontantes_lote=confrontantes_lote_final,
                    json_dados_perimetro=json_dados_perimetro
                )
                arcpy.AddMessage('Fim - Formatando dados perimetro')

                #formatar json de saida
                arcpy.AddMessage('Início - Formatando json de saida')
                json_final = formatar_json_saida(
                    json_entrada=json_entrada,
                    json_saida=json_saida,
                    dados_perimetro=dados_perimetro,
                    pdf_planta=pdf_planta,
                    zip_lote=zip_lote,
                    area_lote=area_lote,
                    perimetro_lote=perimetro_lote,
                    municipios=municipio,
                    municipios_principal=municipio_principal,
                    logradouro=rua,
                    denominacao=lote,
                    n_predial=n_predial,
                    bairro=bairro,
                    fusoutm=codigo_fuso_lote,
                    meridiano_central=meridiano_central,
                    banda=banda_utm,
                    responsavel_tecnico=responsavel_tecnico,
                    funcao=formacao,
                    n_crea_cau=codigo_credenciamento,
                    pronto=pronto
                )
                arcpy.AddMessage('Fim - Formatando json de saida')

                result_json = json.dumps(json_final, ensure_ascii=False)
                arcpy.SetParameter(1, result_json)

                # list(
                #     map(
                #         arcpy.Delete_management,
                #         [scrachgdb, arcpy.env.scratchFolder]
                #     )
                # )

                return result_json


        except Exception as e:
            arcpy.AddError(e)
            # list(
            #     map(
            #         arcpy.Delete_management,
            #         [scrachgdb, arcpy.env.scratchFolder]
            #     )
            # )
            # sys.exit()
            raise e


    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

if __name__ == '__main__':
    # Teste básico de importação
    try:
        import arcpy
        print("ArcPy importado com sucesso")
        
        # Teste de criação da toolbox
        tb = Toolbox()
        print(f"Toolbox criada: {tb.label}")
        
        # Teste de criação da ferramenta
        tool = GerarPlantaREURBTool()
        print(f"Ferramenta criada: {tool.label}")
        
        # Teste de parâmetros
        params = tool.getParameterInfo()
        print(f"Parâmetros: {len(params)}")
        
        print("✓ Todos os testes passaram!")
    except Exception as e:
        print(f"✗ Erro: {str(e)}")
        import traceback
        traceback.print_exc()

    # class Messenger(object):
    #     def addMessage(self, message):
    #         arcpy.AddMessage(message)

    # input_json = '{"identificacaoPlanilha": {"cpfCnpj": "916.742.419-84", "nome": "JOAO MENDES", "lote": "01", "quadra": "01", "endereco": "safasf", "bairro": "teste"},"numeroProcessoColetivo": "050601273/2026"}'
    # #'{"identificacaoPlanilha": {"cpfCnpj": "916.742.419-84", "nome": "JOAO MENDES", "lote": "16", "quadra": "01", "endereco": "safasf", "bairro": "teste"},"numeroProcessoColetivo": "033100029/2026"}'
    # # '{"identificacaoPlanilha": {"cpfCnpj": "334.573.523-72", "nome": "MANOEL PEREIRA DA SILVA", "lote": "01", "quadra": "20", "endereco": "RUA DO PIMENTEL ", "bairro": "SAGRIMA"}, "responsavelTecnico": {"nome": "Luciano Schmitter dos Santos", "formacao": "Arquiteto e Urbanista", "codigoCredenciamento": "A2962543"},"numeroProcessoColetivo": "060503982/2025"}'
    # parameters =[]
    # param0 = arcpy.Parameter()
    # param0.value =input_json
    # parameters.append(param0)

    # GerarPlantaREURBV2 = GerarPlantaREURBTool()
    # GerarPlantaREURBV2.execute(parameters, Messenger())
