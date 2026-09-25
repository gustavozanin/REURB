# -*- coding: utf-8 -*-

"""Fluxo de geração da planta de loteamento (geoserviço e Desktop)."""

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
from exporta_camadas_para_layout import exporta_camadas_para_layout
from tabela_quadras import gerar_tabela_quadras
from tabela_anexo_lotes import gerar_tabela_anexo_lotes
from gerar_planta import gerar_planta, exportar_planta_para_pdf
from formatar_json_saida import formatar_json_saida
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


def executar_geracao_loteamento(
    numero_reurb_coletivo,
    messages=None,
    pasta_saida=None,
    modo='SDE',
    featureserver_url=None,
    formacao_override=None,
    credenciamento_override=None,
    nome_override=None,
    contexto=None,
):
    """
    Executa o fluxo completo de geração da planta de loteamento.
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
    responsavel_tecnico_tabela = _caminho_camadas.responsavel_tecnico_tabela
    municipios_camada = _caminho_camadas.municipios_camada

    if None in [bairro_camada, quadra_camada, lote_camada, eixo_viario_camada]:
        raise ValueError('Caminhos não inicializados corretamente')

    scratchgdb = arcpy.env.scratchGDB
    json_saida = json_saida_modelo

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

        _log(messages, 'Início - Exportando bairro, área e perímetro')
        (
            dir_shapefile,
            bairro_selecionado,
            codigo_fuso_bairro,
            _banda_utm,
            _meridiano_central,
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

        _log(messages, 'Início - Exportando camadas para o layout')
        (
            bairro_layout,
            quadra_layout,
            lote_layout,
            eixo_viario_layout,
        ) = exporta_camadas_para_layout(
            n_reurb_coletivo=numero_reurb_coletivo,
            bairro_feicoes=bairro_camada,
            quadra_feicoes=quadra_camada,
            lote_feicoes=lote_camada,
            eixo_viario=eixo_viario_camada,
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

        _log(messages, 'Início - Gerando tabela de quadras')
        quadra_layout, area_total_quadra, qtd_total_quadra = gerar_tabela_quadras(
            quadra_layout=quadra_layout,
            lote_layout=lote_layout,
            codigo_fuso=codigo_fuso_bairro,
        )
        _log(messages, 'Fim - Gerando tabela de quadras')

        _log(messages, 'Início - Gerando tabela anexo de lotes')
        lote_anexo = gerar_tabela_anexo_lotes(
            lote_layout=lote_layout,
            feicao_dominio=lote_camada,
        )
        _log(messages, 'Fim - Gerando tabela anexo de lotes')

        data_planta = datetime.now().strftime('%d/%m/%Y')
        municipio_nome = municipio_principal['nome']

        _log(messages, 'Início - Gerando planta')
        layout_planta, aprx = gerar_planta(
            bairro_selecionado=bairro_selecionado,
            bairro_layout=bairro_layout,
            quadra_layout=quadra_layout,
            lote_layout=lote_layout,
            eixo_viario_layout=eixo_viario_layout,
            bairro=bairro,
            municipio=municipio_nome,
            numero_reurb_coletivo=numero_reurb_coletivo,
            area=area_bairro,
            perimetro=perimetro_bairro,
            data=data_planta,
            fusoutm=codigo_fuso_bairro,
            responsavel_tecnico=responsavel_tecnico,
            funcao=formacao,
            n_crea_cau=codigo_credenciamento,
            area_total_quadra=area_total_quadra,
            qtd_total_quadra=qtd_total_quadra,
        )
        _log(messages, 'Fim - Gerando planta')

        _log(messages, 'Início - Zipando shapefile')
        zip_lote = zipar_shapefile(dir_shapefile=dir_shapefile)
        _log(messages, 'Fim - Zipando shapefile')

        _log(messages, 'Início - Exportando planta para PDF')
        pdf_planta = exportar_planta_para_pdf(
            layout_planta=layout_planta,
            aprx=aprx,
            numero_reurb_coletivo=numero_reurb_coletivo,
            lote_anexo=lote_anexo,
            municipio=municipio_nome,
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
                prefixo='planta_loteamento',
            )
            return json_resumo_desktop(artefatos, pronto=True)

        _log(messages, 'Início - Formatando JSON de saída')
        json_final = formatar_json_saida(
            numero_reurb_coletivo=numero_reurb_coletivo,
            json_saida=json_saida,
            pdf_planta=pdf_planta,
            zip_lote=zip_lote,
            area_bairro=area_bairro,
            perimetro_bairro=perimetro_bairro,
            municipios=municipio,
            bairro=bairro,
            responsavel_tecnico=responsavel_tecnico,
            funcao=formacao,
            n_crea_cau=codigo_credenciamento,
            pronto=pronto,
        )
        _log(messages, 'Fim - Formatando JSON de saída')
        return json.dumps(json_final, ensure_ascii=False)
