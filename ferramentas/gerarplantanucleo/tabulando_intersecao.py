# -*- coding: utf-8 -*-

import arcpy
import os
import uuid
from pathlib import Path
from variaveis_globais import sirgas2000


def obter_workspace_temporario():
    pasta_temp = Path(__file__).parent.joinpath('temp')
    pasta_temp.mkdir(exist_ok=True)
    gdb_local = pasta_temp.joinpath('reurb_temp.gdb')

    if not gdb_local.exists():
        arcpy.CreateFileGDB_management(str(pasta_temp), gdb_local.name)

    return str(gdb_local)


def _workspaces_intermediarios():
    workspaces = ['memory']

    try:
        workspaces.append(obter_workspace_temporario())
    except Exception as e:
        arcpy.AddWarning(f'Nao foi possivel criar GDB temporaria local: {str(e)}')

    try:
        if arcpy.env.scratchGDB:
            workspaces.append(arcpy.env.scratchGDB)
    except Exception:
        pass

    return workspaces

def tabulacao_intersecao(
        feicao_perimetro: os.PathLike,
        intersecao_dissolvida: os.PathLike,
        class_fields: list,
        area: float
    ) -> os.PathLike:
    """
    Realiza o calculo percentual de interseção das área de analise para bloqueio.

    -------
    Parameters:
        feicao_perimetro(os.PathLike):
            Caminho para a camada que contém o perímetro a ser analisado no processo de regularização fundiária.
        intersecao_dissolvida(os.PathLike):
            Caminho para a camada de interseção que será estimado o percentual.
        class_fields(os.PathLike):
            Nomenclatura das colunas que seram utilizadas para a união (dissolve) das feições.
        area(float):
            Valor de área para o perímetro avaliado no processo.

    -------
    Returns:
        os.PathLike
    """
    sufixo = uuid.uuid4().hex[:8]
    ultimo_erro = None

    for workspace in _workspaces_intermediarios():
        feicao_intersecao_saida = os.path.join(workspace, f'feicao_intersecao_{sufixo}')
        somatorio_area_saida = os.path.join(workspace, f'somatorio_area_{sufixo}')

        try:
            feicao_intersecao = arcpy.PairwiseClip_analysis(
                in_features=intersecao_dissolvida,
                clip_features=feicao_perimetro,
                out_feature_class=feicao_intersecao_saida
            )

            arcpy.CalculateGeometryAttributes_management(
                in_features=feicao_intersecao,
                geometry_property=[
                    ['area_inter', 'AREA_GEODESIC']
                ],
                area_unit='SQUARE_METERS',
                coordinate_system=sirgas2000
            )

            somatorio_area = arcpy.Statistics_analysis(
                in_table=feicao_intersecao,
                out_table=somatorio_area_saida,
                statistics_fields=[
                    ['area_inter', 'SUM']
                ],
                case_field=class_fields
            )

            expressao = f"round((!SUM_area_inter! / {area}) * 100, 2)"
            arcpy.CalculateField_management(
                in_table=somatorio_area,
                field='porcentagem',
                expression=expressao,
                expression_type='PYTHON3',
                field_type='SHORT'
            )

            return somatorio_area
        except Exception as e:
            ultimo_erro = e
            arcpy.AddWarning(f'Falha ao criar intersecao em {workspace}. Tentando proximo workspace. Detalhe: {str(e)}')

    raise ultimo_erro
