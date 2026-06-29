# -*- coding: utf-8 -*-

import arcpy

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Gestao Equipe"
        self.alias = "GestaoEquipe"

        # List of tool classes associated with this toolbox
        self.tools = [GestaoEquipeTool]

class GestaoEquipeTool:
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "GestaoEquipeTool"
        self.description = "Ferramenta utilizada para gestão e produção de equipe por núcleo/reurb coletivo"
        self.canRunInBackground = True

    def getParameterInfo(self):
        """Define the tool parameters."""
        json_entrada = arcpy.Parameter(
            name='json_entrada',
            displayName='json_entrada',
            direction='Input',
            datatype='GPString',
            parameterType='Required'
        )

        json_saida = arcpy.Parameter(
            name='json_saida',
            displayName='json_saida',
            direction='Output',
            datatype='GPString',
            parameterType='Derived'
        )

        params = []
        params.append(json_entrada)
        params.append(json_saida)

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
            from validar_json import validar_json
            from caminho_camadas import (
                inicializar_caminhos,
                bairro_camada,
                quadra_camada,
                lote_camada,
            )
            from sql_utils import clausula_n_coletivo
            from check_nucleo import check_nucleo
            from check_reurb_coletivo import check_reurb_coletivo
            from check_quadras_lotes import check_quadras_lotes
            from check_contencao_espacial import check_contencao_espacial
            from calcular_gestao_equipe import calcular_gestao_equipe
            from formatar_json_saida import formatar_json_saida
        except Exception as e:
            arcpy.AddError(f"Erro ao importar módulos: {str(e)}")
            raise

        try:
            inicializar_caminhos()
        except Exception as e:
            arcpy.AddError(f"Erro ao inicializar caminhos: {str(e)}")
            raise

        if not bairro_camada or not quadra_camada or not lote_camada:
            arcpy.AddError('Erro: Caminhos das camadas não foram inicializados corretamente')
            raise ValueError('Caminhos não inicializados')
        arcpy.AddMessage('Início - Validando JSON de entrada')

        try:
            numero_reurb_coletivo = validar_json(parameters[0].valueAsText)
        except ValueError as e:
            arcpy.AddError(str(e))
            raise
        arcpy.AddMessage('Fim - Validando JSON de entrada')

        scratchgdb = arcpy.env.scratchGDB

        where_clause = clausula_n_coletivo(numero_reurb_coletivo)

        with arcpy.EnvManager(workspace=scratchgdb, overwriteOutput=True):
            arcpy.AddMessage('Início - Preparando camadas temporárias')
            nucleo_lyr = arcpy.MakeFeatureLayer_management(
                in_features=bairro_camada,
                out_layer='gestao_nucleo_lyr',
                
                where_clause=where_clause
            )[0]
            quadras_lyr = arcpy.MakeFeatureLayer_management(
                in_features=quadra_camada,
                out_layer='gestao_quadras_lyr',
                where_clause=where_clause
            )[0]
            lotes_lyr = arcpy.MakeFeatureLayer_management(
                in_features=lote_camada,
                out_layer='gestao_lotes_lyr',
                where_clause=where_clause
            )[0]

            arcpy.SelectLayerByAttribute_management(
                in_layer_or_view=nucleo_lyr,
                selection_type='NEW_SELECTION',
                where_clause=where_clause
            )

            arcpy.SelectLayerByAttribute_management(
                in_layer_or_view=quadras_lyr,
                selection_type='NEW_SELECTION',
                where_clause=where_clause
            )

            arcpy.SelectLayerByAttribute_management(
                in_layer_or_view=lotes_lyr,
                selection_type='NEW_SELECTION',
                where_clause=where_clause
            )
            arcpy.AddMessage('Fim - Preparando camadas temporárias')

            arcpy.AddMessage('Início - Verificando existência do núcleo')
            if not check_nucleo(nucleo_lyr):
                raise arcpy.ExecuteError
            arcpy.AddMessage('Fim - Verificando existência do núcleo')

            arcpy.AddMessage('Início - Verificando quadras e lotes')
            if not check_quadras_lotes(quadras_lyr, lotes_lyr, lote_camada):
                raise arcpy.ExecuteError
            arcpy.AddMessage('Fim - Verificando quadras e lotes')

            arcpy.AddMessage('Início - Verificando número do REURB coletivo nos lotes')
            if not check_reurb_coletivo(lotes_lyr, numero_reurb_coletivo):
                raise arcpy.ExecuteError
            arcpy.AddMessage('Fim - Verificando número do REURB coletivo nos lotes')

            arcpy.AddMessage('Início - Verificando contenção espacial no núcleo')
            if not check_contencao_espacial(
                nucleo_lyr, quadras_lyr, lotes_lyr, numero_reurb_coletivo
            ):
                arcpy.AddError('Quadra ou Lote fora do perímetro do Núcleo')
            arcpy.AddMessage('Fim - Verificando contenção espacial no núcleo')

            arcpy.AddMessage('Início - Calculando gestão de equipe por quadra')
            quadras_resultado = calcular_gestao_equipe(quadras_lyr, lotes_lyr)
            arcpy.AddMessage('Fim - Calculando gestão de equipe por quadra')

        arcpy.AddMessage('Início - Formatando JSON de saída')
        json_saida = formatar_json_saida(quadras_resultado)
        arcpy.AddMessage('Fim - Formatando JSON de saída')

        arcpy.SetParameter(1, json_saida)
        # print(json_saida)

        return json_saida

    def postExecute(self, parameters):
        """This method takes place after outputs are processed and
        added to the display."""
        return

if __name__ == "__main__":
    # Teste básico de importação
    try:
        import arcpy
        print("ArcPy importado com sucesso")
        
        # Teste de criação da toolbox
        tb = Toolbox()
        print(f"Toolbox criada: {tb.label}")
        
        # Teste de criação da ferramenta
        tool = GestaoEquipeTool()
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

    # input_json = '{"numeroProcessoColetivo": "051201571/2026"}'
    # # '{"identificacaoPlanilha": {"cpfCnpj": "334.573.523-72", "nome": "MANOEL PEREIRA DA SILVA", "lote": "01", "quadra": "20", "endereco": "RUA DO PIMENTEL ", "bairro": "SAGRIMA"}, "responsavelTecnico": {"nome": "Luciano Schmitter dos Santos", "formacao": "Arquiteto e Urbanista", "codigoCredenciamento": "A2962543"},"numeroProcessoColetivo": "060503982/2025"}'
    # parameters =[]
    # param0 = arcpy.Parameter()
    # param0.value = input_json
    # parameters.append(param0)

    # GerarPlantaREURBV2 = GestaoEquipeTool()
    # GerarPlantaREURBV2.execute(parameters, Messenger())
