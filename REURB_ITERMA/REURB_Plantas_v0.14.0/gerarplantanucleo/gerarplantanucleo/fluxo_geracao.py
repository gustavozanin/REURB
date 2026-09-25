# -*- coding: utf-8 -*-

"""Fluxo de geração da planta núcleo (geoserviço e Desktop)."""

import json
import arcpy
from datetime import datetime

import caminho_camadas as _caminho_camadas
from tabela_modelo import json_saida_modelo
from check_reurb_coletivo import check_reurb_coletivo
from check_status import check_status
from check_responsavel import check_responsavel_tecnico
from exporta_shapefile import exporta_shapefile, zipar_shapefile
from municipalidade import municipalidade
from transforma_feicao import transforma_feicao
from azminute import azimute
from confrontantes import confrontantes
from formatar_tabela_atributos import formatar_tabela_atributos
from exporta_camadas_para_layout import exporta_camadas_para_layout
from tabela_quadras import gerar_tabela_quadras
from gerar_planta import gerar_planta, exportar_planta_para_pdf
from formatar_json_saida import formatar_json_saida
from formatar_dados_perimetro import formatar_dados_perimetro
from transforma_vertices_em_linhas import transforma_vertices_em_linhas
from salvar_artefatos_desktop import (
    salvar_artefatos_desktop,
    json_resumo_desktop,
)


def _log(messages, texto):
    if messages is not None and hasattr(messages, 'AddMessage'):
        messages.AddMessage(texto)
    else:
        arcpy.AddMessage(texto)


def _erro(messages, texto):
    if messages is not None and hasattr(messages, 'AddError'):
        messages.AddError(texto)
    else:
        arcpy.AddError(texto)


def executar_geracao_nucleo(
    numero_reurb_coletivo,
    messages=None,
    pasta_saida=None,
    modo='SDE',
    featureserver_url=None,
    formacao_override=None,
    credenciamento_override=None,
    nome_override=None,
    incluir_base64=True,
    contexto=None,
):
    """
    Executa o fluxo completo de geração da planta núcleo.

    Args:
        numero_reurb_coletivo: número do processo coletivo.
        messages: objeto com AddMessage/AddError (toolbox).
        pasta_saida: se informado, grava PDF/ZIP nessa pasta (modo Desktop).
        modo: 'SDE' ou 'FEATURESERVER'.
        featureserver_url: URL base do FeatureServer.
        formacao_override / credenciamento_override / nome_override: opcionais no Desktop.
        incluir_base64: se True, JSON de saída traz PDF/ZIP em base64 (geoserviço).
        contexto: corrida Desktop isolada (scratch/pasta/diário).

    Returns:
        str JSON de saída.
    """
    _caminho_camadas.inicializar_caminhos(
        modo=modo,
        featureserver_url=featureserver_url,
        forcar=True,
    )

    bairro_camada = _caminho_camadas.bairro_camada
    quadra_camada = _caminho_camadas.quadra_camada
    lote_camada = _caminho_camadas.lote_camada
    eixo_viario_camada = _caminho_camadas.eixo_viario_camada
    confrontante_camada = _caminho_camadas.confrontante_camada
    responsavel_tecnico_tabela = _caminho_camadas.responsavel_tecnico_tabela
    municipios_camada = _caminho_camadas.municipios_camada

    if None in [
        bairro_camada,
        quadra_camada,
        lote_camada,
        eixo_viario_camada,
        confrontante_camada,
    ]:
        raise ValueError('Caminhos não inicializados corretamente')

    scratchgdb = arcpy.env.scratchGDB
    json_saida = json_saida_modelo
    json_entrada = {'numeroProcessoColetivo': numero_reurb_coletivo}

    with arcpy.EnvManager(workspace=scratchgdb, overwriteOutput=True):
        _log(messages, 'Início - Verificando se o número do REURB coletivo existe')
        if check_reurb_coletivo(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        ) is False:
            json_saida['pronto'] = False
            if pasta_saida:
                return json_resumo_desktop(
                    {'numeroProcessoColetivo': numero_reurb_coletivo},
                    pronto=False,
                )
            return json.dumps(json_saida, ensure_ascii=False)
        _log(messages, 'Fim - Verificando se o número do REURB coletivo existe')

        _log(messages, 'Início - Verificando se o bairro está pronto')
        pronto = check_status(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        )
        if pronto is False:
            json_saida['pronto'] = pronto
            if pasta_saida:
                return json_resumo_desktop(
                    {'numeroProcessoColetivo': numero_reurb_coletivo},
                    pronto=False,
                )
            return json.dumps(json_saida, ensure_ascii=False)
        _log(messages, 'Fim - Verificando se o bairro está pronto')

        _log(messages, 'Início - Verificando se o responsável técnico existe')
        (
            responsavel_tecnico_existe,
            responsavel_tecnico,
            formacao,
            codigo_credenciamento,
        ) = check_responsavel_tecnico(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
            responsavel_tecnico_tabela=responsavel_tecnico_tabela,
            formacao_override=formacao_override or None,
            credenciamento_override=credenciamento_override or None,
            nome_override=nome_override or None,
        )
        if responsavel_tecnico_existe is False:
            _erro(
                messages,
                f'Responsável técnico {responsavel_tecnico} não cadastrado '
                f'ou preenchimento incorreto',
            )
            json_saida['pronto'] = False
            if pasta_saida:
                return json_resumo_desktop(
                    {'numeroProcessoColetivo': numero_reurb_coletivo},
                    pronto=False,
                )
            return json.dumps(json_saida, ensure_ascii=False)
        _log(messages, 'Fim - Verificando se o responsável técnico existe')

        _log(
            messages,
            'Início - Exportando bairro, fuso UTM, área e perímetro',
        )
        (
            dir_shapefile,
            bairro_selecionado,
            codigo_fuso_bairro,
            banda_utm,
            meridiano_central,
            area_bairro,
            perimetro_bairro,
            bairro,
        ) = exporta_shapefile(
            numero_reurb_coletivo=numero_reurb_coletivo,
            feicoes_bairro=bairro_camada,
        )
        _log(messages, 'Fim - Exportando bairro')

        _log(messages, 'Início - Selecionando município')
        municipio, municipio_principal = municipalidade(
            feicao_perimetro=bairro_selecionado,
            municipios=municipios_camada,
            area=area_bairro,
        )
        _log(messages, 'Fim - Selecionando município')

        _log(messages, 'Início - Transformando bairro em linha e vértices')
        vertices_feicao = transforma_feicao(feicao_perimetro=bairro_selecionado)
        _log(messages, 'Fim - Transformando bairro em linha e vértices')

        _log(messages, 'Início - Calculando azimute e distância')
        azimute(feicao_entrada=vertices_feicao)
        _log(messages, 'Fim - Calculando azimute e distância')

        _log(messages, 'Início - Transformando vértices em linhas')
        confrontantes_bairro = transforma_vertices_em_linhas(
            vertices_bairro=vertices_feicao
        )
        _log(messages, 'Fim - Transformando vértices em linhas')

        _log(messages, 'Início - Encontrando confrontantes')
        confrontantes(
            feicao_entrada=confrontantes_bairro,
            n_coletivo=numero_reurb_coletivo,
            bairro_feicoes=bairro_camada,
            confrontante_feicoes=confrontante_camada,
            eixo_viario=eixo_viario_camada,
        )
        _log(messages, 'Fim - Encontrando confrontantes')

        _log(messages, 'Início - Formatando tabela de atributos')
        confrontantes_bairro_final = formatar_tabela_atributos(
            feicao_entrada=confrontantes_bairro
        )
        _log(messages, 'Fim - Formatando tabela de atributos')

        _log(messages, 'Início - Exportando camadas para o layout')
        bairro_layout, quadra_layout, lote_layout = exporta_camadas_para_layout(
            n_reurb_coletivo=numero_reurb_coletivo,
            bairro_feicoes=bairro_camada,
            quadra_feicoes=quadra_camada,
            lote_feicoes=lote_camada,
        )
        _log(messages, 'Fim - Exportando camadas para o layout')
        if contexto is not None:
            contexto.diagnosticar_selecao(
                numero_reurb_coletivo=numero_reurb_coletivo,
                quadra_origem=quadra_camada,
                lote_origem=lote_camada,
                bairro_layout=bairro_layout,
                quadra_layout=quadra_layout,
                lote_layout=lote_layout,
                messages=messages,
            )

        _log(messages, 'Início - Gerando tabela resumo de quadras')
        quadra_layout, area_total_quadra, qtd_total_quadra = gerar_tabela_quadras(
            quadra_layout=quadra_layout,
            lote_layout=lote_layout,
            codigo_fuso=codigo_fuso_bairro,
        )
        _log(messages, 'Fim - Gerando tabela resumo de quadras')

        data_planta = datetime.now().strftime('%d/%m/%Y')
        _log(messages, 'Início - Gerando planta')
        layout_planta, aprx_planta = gerar_planta(
            bairro_selecionado=bairro_selecionado,
            confrontantes_bairro=confrontantes_bairro_final,
            vertices_bairro=vertices_feicao,
            quadra_layout=quadra_layout,
            lote_layout=lote_layout,
            area_total_quadra=area_total_quadra,
            qtd_total_quadra=qtd_total_quadra,
            bairro=bairro,
            municipio=municipio_principal['nome'],
            area=area_bairro,
            processo=numero_reurb_coletivo,
            folha='01',
            perimetro=perimetro_bairro,
            data=data_planta,
            fusoutm=codigo_fuso_bairro,
            responsavel_tecnico=responsavel_tecnico,
            funcao=formacao,
            n_crea_cau=codigo_credenciamento,
        )
        _log(messages, 'Fim - Gerando planta')

        _log(messages, 'Início - Zipando shapefile')
        zip_lote = zipar_shapefile(dir_shapefile=dir_shapefile)
        _log(messages, 'Fim - Zipando shapefile')

        _log(messages, 'Início - Exportando planta para PDF')
        pdf_planta = exportar_planta_para_pdf(
            layout_planta=layout_planta,
            aprx=aprx_planta,
            numero_reurb_coletivo=numero_reurb_coletivo,
            confrontantes_bairro=confrontantes_bairro_final,
            municipio=municipio_principal['nome'],
            bairro=bairro,
            area=area_bairro,
            perimetro=perimetro_bairro,
            data=data_planta,
            responsavel_tecnico=responsavel_tecnico,
            funcao=formacao,
            n_crea_cau=codigo_credenciamento,
        )
        _log(messages, 'Fim - Exportando planta para PDF')

        if pasta_saida:
            artefatos = salvar_artefatos_desktop(
                pasta_saida=pasta_saida,
                numero_reurb_coletivo=numero_reurb_coletivo,
                pdf_planta=pdf_planta,
                zip_lote=zip_lote,
                prefixo='planta_nucleo',
            )
            return json_resumo_desktop(artefatos, pronto=True)

        _log(messages, 'Início - Formatando dados perímetro')
        dados_perimetro = formatar_dados_perimetro(
            confrontantes_bairro=confrontantes_bairro_final
        )
        _log(messages, 'Fim - Formatando dados perímetro')

        _log(messages, 'Início - Formatando JSON de saída')
        if not incluir_base64:
            json_saida['identificacaoPlanilha']['imagemPlanta'] = str(pdf_planta)
            json_saida['identificacaoPlanilha']['zipShapePlanta'] = str(zip_lote)

        json_final = formatar_json_saida(
            numero_reurb_coletivo=numero_reurb_coletivo,
            bairro=bairro,
            json_entrada=json_entrada,
            json_saida=json_saida,
            dados_perimetro=dados_perimetro,
            pdf_planta=pdf_planta,
            zip_lote=zip_lote,
            area_bairro=area_bairro,
            perimetro_bairro=perimetro_bairro,
            municipios=municipio,
            municipios_principal=municipio_principal,
            fusoutm=codigo_fuso_bairro,
            meridiano_central=meridiano_central,
            banda=banda_utm,
            responsavel_tecnico=responsavel_tecnico,
            funcao=formacao,
            n_crea_cau=codigo_credenciamento,
            pronto=pronto,
        )
        _log(messages, 'Fim - Formatando JSON de saída')
        return json.dumps(json_final, ensure_ascii=False)
