# -*- coding: utf-8 -*-
"""Fluxo de geração da planta institucional de lote (Desktop).

`executar_geracao_institucional` liga ponta a ponta:

    1. `caminho_camadas.inicializar_caminhos` (modo FEATURESERVER)
    2. checks de REURB / status / responsável / lote institucional
    3. exportação UTM do lote e da quadra + medidas
    4. `pipeline_perimetro.montar_tabela_segmentos_de_vertices` via
       `motor_perimetro` + `confrontantes_lote`
    5. CSV (`quadro_coordenadas.exportar_csv`), memorial narrativo,
       ZIP de shapefiles
    6. planta A3 institucional + memorial/quadro/termo via ReportLab
       + `exportar_pdf_unificado.exportar_pacote_final`
    7. `salvar_artefatos_desktop` na pasta do analista

Regra de `pronto`: CSV e ZIP são copiados sempre que a geometria roda;
o PDF só quando o layout A3 atende ao contrato. `pronto=True` exige
PDF+CSV+ZIP.
"""

import json
import os
from datetime import datetime

import arcpy

import caminho_camadas as _caminho_camadas
from check_reurb_coletivo import check_reurb_coletivo
from check_status import check_status
from check_responsavel import check_responsavel_tecnico
from exporta_shapefile import (
    exportar_camadas_do_perimetro,
    zipar_shapefile,
)
from municipalidade import municipalidade
from formatar_dados_perimetro import formatar_dados_perimetro
from quadro_coordenadas import exportar_csv as exportar_csv_quadro
from memorial_narrativo import gerar_texto_memorial
from gerar_planta_perimetro import LayoutConfigurationError
from gerar_planta_institucional import (
    gerar_planta_institucional,
    exportar_planta_institucional_para_pdf,
    exportar_lotes_quadra,
)
from exportar_pdf_unificado import exportar_pacote_final, planejar_folhas
from salvar_artefatos_desktop import salvar_artefatos_memorial
from documentos_pdf import gerar_memorial as gerar_memorial_pdf
from documentos_pdf import gerar_quadro as gerar_quadro_pdf
from documentos_pdf import gerar_termo_autenticacao
from autenticacao_documentos import montar_selo

DENSIDADES_VALIDAS = ('integral', 'simplificado')

# UF fixa do órgão (ITERMA/MA) — mesma convenção usada no cabeçalho do
# memorial narrativo (ver `memorial_narrativo._montar_cabecalho`).
UF_PADRAO = 'MA'


def _resultado_json(
    numero_reurb_coletivo,
    densidade,
    tolerancia_m,
    pronto,
    mensagem,
    pdf='',
    csv='',
    zip_='',
    extra=None,
):
    """Resumo JSON padronizado da toolbox Desktop."""
    payload = {
        'pronto': pronto,
        'numeroProcessoColetivo': numero_reurb_coletivo,
        'densidade': densidade,
        'toleranciaM': tolerancia_m,
        'pdf': pdf,
        'csv': csv,
        'zip': zip_,
        'mensagem': mensagem,
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


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


def _sincronizar_medidas_perimetro(
    feicao_perimetro, auditoria_geometrica, meta, messages=None
):
    """Usa em todos os artefatos as medidas da poligonal descrita."""
    area = round(float(auditoria_geometrica['areaCoordenadasM2']), 2)
    perimetro = round(
        float(auditoria_geometrica['perimetroCoordenadasM']), 2
    )
    meta['area_m2'] = area
    meta['perimetro_m'] = perimetro

    campos = {
        campo.name.lower(): campo.name
        for campo in arcpy.ListFields(feicao_perimetro)
    }
    area_field = campos.get('area_m2')
    perimeter_field = campos.get('perimetro')
    if area_field and perimeter_field:
        with arcpy.da.UpdateCursor(
            feicao_perimetro, [area_field, perimeter_field]
        ) as cursor:
            for row in cursor:
                row[0], row[1] = area, perimetro
                cursor.updateRow(row)
    else:
        _log(
            messages,
            'Aviso: campos area_m2/perimetro não encontrados no shapefile; '
            'PDF e auditoria foram sincronizados.',
        )
    return area, perimetro

def executar_geracao_institucional(
    numero_reurb_coletivo,
    quadra,
    lote,
    pasta_saida,
    messages=None,
    featureserver_url=None,
    nome_override=None,
    formacao_override=None,
    credenciamento_override=None,
    densidade='integral',
    tolerancia_m=0.5,
):
    """Gera documentação cartorial de um lote institucional (Desktop).

    T1: checks + resolução do lote. T2.1: perímetro UTM do lote + CSV/ZIP.
    PDF unificado (planta A3) completa em T2.3; memorial narrativo já sai
    no pacote PDF quando T2.3 ligar — nesta etapa CSV/ZIP + texto memorial
    no log/meta.
    """
    from check_lote_institucional import (
        LoteInstitucionalErro,
        resolver_lote_institucional,
    )
    from exporta_shapefile import exporta_lote_institucional
    from salvar_artefatos_desktop import salvar_artefatos_institucional
    import pipeline_perimetro

    def _aviso(texto):
        if messages is not None and hasattr(messages, 'AddWarning'):
            messages.AddWarning(texto)
        else:
            arcpy.AddWarning(texto)

    def _resultado(pronto, mensagem, pdf='', csv='', zip_=''):
        return _resultado_json(
            numero_reurb_coletivo=numero_reurb_coletivo,
            densidade=densidade,
            tolerancia_m=tolerancia_m,
            pronto=pronto,
            mensagem=mensagem,
            pdf=pdf,
            csv=csv,
            zip_=zip_,
            extra={'quadra': quadra, 'lote': lote},
        )

    erros = []
    if not (numero_reurb_coletivo or '').strip():
        erros.append('numero_reurb vazio')
    if quadra is None or str(quadra).strip() == '':
        erros.append('quadra vazia')
    if not (lote or '').strip():
        erros.append('lote vazio')
    if not pasta_saida:
        erros.append('pasta_saida vazia')
    if densidade not in DENSIDADES_VALIDAS:
        erros.append(f'densidade inválida: {densidade}')
    if erros:
        for erro in erros:
            _log(messages, f'Erro de validação: {erro}')
        return _resultado(False, 'Parâmetros inválidos: ' + '; '.join(erros))

    _caminho_camadas.inicializar_caminhos(
        modo='FEATURESERVER',
        featureserver_url=featureserver_url,
        forcar=True,
    )

    bairro_camada = _caminho_camadas.bairro_camada
    lote_camada = _caminho_camadas.lote_camada
    eixo_viario_camada = _caminho_camadas.eixo_viario_camada
    confrontante_camada = _caminho_camadas.confrontante_camada
    responsavel_tecnico_tabela = _caminho_camadas.responsavel_tecnico_tabela
    municipios_camada = _caminho_camadas.municipios_camada

    if None in [
        bairro_camada,
        lote_camada,
        eixo_viario_camada,
        confrontante_camada,
        responsavel_tecnico_tabela,
        municipios_camada,
    ]:
        raise ValueError('Caminhos não inicializados corretamente')

    scratchgdb = arcpy.env.scratchGDB
    scratch_folder = arcpy.env.scratchFolder

    with arcpy.EnvManager(workspace=scratchgdb, overwriteOutput=True):
        _log(messages, 'Início - Verificando REURB coletivo')
        if check_reurb_coletivo(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        ) is False:
            return _resultado(False, 'Número do REURB coletivo inexistente.')

        _log(messages, 'Início - Verificando status do bairro')
        if check_status(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        ) is False:
            return _resultado(
                False, 'Bairro em andamento (status diferente de 2 ou 4).'
            )

        _log(messages, 'Início - Verificando responsável técnico')
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
                f'Responsável técnico "{responsavel_tecnico}" não cadastrado '
                f'ou preenchimento incorreto',
            )
            return _resultado(
                False,
                f'Responsável técnico "{responsavel_tecnico}" não cadastrado '
                f'ou preenchimento incorreto',
            )

        _log(messages, 'Início - Resolvendo lote institucional')
        try:
            lote_info = resolver_lote_institucional(
                lote_camada,
                numero_reurb_coletivo,
                quadra,
                lote,
            )
        except LoteInstitucionalErro as e:
            _erro(messages, str(e))
            return _resultado(False, str(e))

        for aviso in lote_info.get('avisos') or []:
            _aviso(aviso)

        titulo = lote_info['titulo']
        if not (lote_info.get('nome') or '').strip():
            _aviso(f'Nome do lote vazio; usando título fallback: {titulo}')

        _log(
            messages,
            'Lote institucional resolvido: '
            f"{titulo} | {lote_info['status_rotulo']} | "
            f"Q{lote_info['quadra']}/L{lote_info['lote']}",
        )

        _log(messages, 'Início - Exportando lote UTM + linearização de arcos')
        (
            dir_shapefile,
            lote_selecionado,
            codigo_fuso,
            _banda_utm,
            meridiano_central,
            area_lote,
            perimetro_lote,
            bairro_attr,
            _nome_export,
        ) = exporta_lote_institucional(
            numero_reurb_coletivo=numero_reurb_coletivo,
            feicoes_lote=lote_camada,
            quadra=quadra,
            lote=lote,
            where_clause=lote_info.get('where'),
        )
        _log(messages, 'Fim - Exportando lote')

        _log(messages, 'Início - Selecionando município')
        _municipios, municipio_principal = municipalidade(
            feicao_perimetro=lote_selecionado,
            municipios=municipios_camada,
            area=area_lote,
        )
        _log(messages, 'Fim - Selecionando município')

        meta = {
            'numero_reurb': numero_reurb_coletivo,
            'bairro': bairro_attr,
            'municipio': municipio_principal.get('nome'),
            'uf': UF_PADRAO,
            'area_m2': area_lote,
            'perimetro_m': perimetro_lote,
            'fuso': codigo_fuso,
            'meridiano_central': meridiano_central,
            'densidade': densidade,
            'rt_nome': responsavel_tecnico,
            'rt_formacao': formacao,
            'rt_crea': codigo_credenciamento,
            'nome': lote_info.get('nome'),
            'titulo': titulo,
            'quadra': lote_info.get('quadra', quadra),
            'lote': lote_info.get('lote', lote),
            'status_rotulo': lote_info.get('status_rotulo'),
            'rua': lote_info.get('rua') or '',
        }

        _log(
            messages,
            'Início - Vértices, azimute UTM, segmentos e confrontantes (lote)',
        )
        tabela_final, vertices_lote, auditoria_geometrica = (
            pipeline_perimetro.montar_tabela_segmentos_de_vertices(
                feicao_perimetro=lote_selecionado,
                n_coletivo=numero_reurb_coletivo,
                bairro_feicoes=bairro_camada,
                confrontante_feicoes=confrontante_camada,
                eixo_viario=eixo_viario_camada,
                densidade=densidade,
                tolerancia_m=tolerancia_m,
                messages=messages,
                lote_feicoes=lote_camada,
                quadra=lote_info.get('quadra', quadra),
                lote=lote_info.get('lote', lote),
            )
        )
        _log(messages, 'Fim - Pipeline geométrico do lote')

        area_lote, perimetro_lote = _sincronizar_medidas_perimetro(
            lote_selecionado, auditoria_geometrica, meta, messages
        )
        _log(
            messages,
            'Área e perímetro sincronizados com a poligonal descrita: '
            f'{area_lote:.2f} m²; {perimetro_lote:.2f} m',
        )

        from constantes import CONFRONTANTE_PADRAO

        dados_perimetro = formatar_dados_perimetro(confrontantes_bairro=tabela_final)
        auditoria_geometrica['segmentosComConfrontante'] = sum(
            1
            for item in dados_perimetro
            if item.get('confrontante')
            and item.get('confrontante') != CONFRONTANTE_PADRAO
        )
        auditoria_geometrica['segmentosPadraoNaoIdentificado'] = sum(
            1
            for item in dados_perimetro
            if item.get('confrontante') == CONFRONTANTE_PADRAO
        )
        auditoria_geometrica['segmentosSemConfrontante'] = sum(
            1 for item in dados_perimetro if not item.get('confrontante')
        )

        slug = (
            f'{numero_reurb_coletivo.replace("/", "_")}'
            f'_Q{quadra}_L{lote}'
        )

        _log(messages, 'Início - CSV do quadro de coordenadas')
        csv_scratch = os.path.join(
            scratch_folder, f'quadro_institucional_{slug}.csv'
        )
        exportar_csv_quadro(dados_perimetro, csv_scratch)

        _log(messages, 'Início - Texto do memorial (cabeçalho institucional)')
        texto_memorial = gerar_texto_memorial(dados_perimetro, meta=meta)
        # AD-016: só alerta se o texto livre de Observação vazou no memorial
        obs = lote_info.get('observacao')
        if obs is not None:
            obs_txt = str(obs).strip()
            if (
                obs_txt
                and obs_txt.lower() not in ('<nulo>', 'none', 'null')
                and len(obs_txt) >= 8
                and obs_txt in texto_memorial
            ):
                _aviso(
                    'Texto de Observação detectado no memorial; '
                    'revisar montagem do cabeçalho.'
                )

        _log(messages, 'Início - ZIP shapefile (lote + vértices + segmentos)')
        exportar_camadas_do_perimetro(
            dir_shapefile=dir_shapefile,
            numero_reurb_coletivo=slug,
            vertices=vertices_lote,
            segmentos=tabela_final,
        )
        zip_scratch = zipar_shapefile(dir_shapefile=dir_shapefile)

        _log(messages, 'Início - Selando a emissão (protocolo + hash)')
        selo = montar_selo(
            dados_perimetro,
            meta,
            datetime.now(),
            arquivos={
                'CSV do quadro': csv_scratch,
                'ZIP do shapefile': zip_scratch,
            },
        )
        _log(messages, f"Protocolo da emissão: {selo['protocolo']}")

        # Layout institucional não traz a tabela completa na planta A3:
        # o Quadro de Confrontações sempre entra no PDF unificado.
        plano_folhas = planejar_folhas(
            len(dados_perimetro), forcar_anexo=True
        )
        pdf_unificado_scratch = None
        mensagem_pdf = None
        _log(
            messages,
            'Início - Gerando PDF unificado (planta + quadro + memorial + termo)',
        )
        try:
            data_planta = datetime.now().strftime('%d/%m/%Y')
            _log(messages, 'Exportando lotes da quadra para overview')
            lotes_quadra = exportar_lotes_quadra(
                lote_camada, numero_reurb_coletivo, quadra
            )
            # Planta A3: layout de lote individual (gerarplantareurb)
            layout_planta, aprx = gerar_planta_institucional(
                lote_selecionado=lote_selecionado,
                confrontantes_lote=tabela_final,
                vertices_lote=vertices_lote,
                lotes_quadra=lotes_quadra,
                interessado=titulo,
                interessado_cpf=None,
                bairro=bairro_attr or '',
                municipio=municipio_principal.get('nome'),
                denominacao=lote_info.get('rua') or '',
                quadra=lote_info.get('quadra', quadra),
                lote=lote_info.get('lote', lote),
                area=area_lote,
                perimetro=perimetro_lote,
                data=data_planta,
                fusoutm=codigo_fuso,
                responsavel_tecnico=responsavel_tecnico,
                funcao=formacao,
                n_crea_cau=codigo_credenciamento,
            )
            pdf_planta = exportar_planta_institucional_para_pdf(
                layout_planta,
                os.path.join(scratch_folder, 'planta_institucional.pdf'),
            )

            pdf_quadro = gerar_quadro_pdf(
                dados_perimetro,
                meta,
                os.path.join(scratch_folder, 'quadro_coordenadas.pdf'),
                folha=plano_folhas['folha_quadro'],
                selo=selo,
            )

            pdf_memorial = gerar_memorial_pdf(
                dados_perimetro,
                meta,
                os.path.join(scratch_folder, 'memorial.pdf'),
                selo=selo,
            )

            pdf_termo = gerar_termo_autenticacao(
                meta,
                selo,
                os.path.join(scratch_folder, 'termo_autenticacao.pdf'),
            )

            pdf_unificado_scratch = os.path.join(
                scratch_folder, f'planta_institucional_{slug}.pdf'
            )
            exportar_pacote_final(
                pdf_planta,
                pdf_quadro,
                pdf_memorial,
                pdf_unificado_scratch,
                termo=pdf_termo,
            )
            _log(messages, 'Fim - Gerando PDF unificado')
            _ = aprx
        except LayoutConfigurationError as e:
            mensagem_pdf = str(e)
            pdf_unificado_scratch = None
            _log(messages, f'PDF unificado pendente (layout): {mensagem_pdf}')
        except RuntimeError as e:
            mensagem_pdf = str(e)
            pdf_unificado_scratch = None
            _log(messages, f'PDF unificado pendente: {mensagem_pdf}')

        artefatos = salvar_artefatos_institucional(
            pasta_saida=pasta_saida,
            numero_reurb_coletivo=numero_reurb_coletivo,
            quadra=quadra,
            lote=lote,
            pdf_unificado=pdf_unificado_scratch,
            csv_quadro=csv_scratch,
            zip_shapefile=zip_scratch,
        )

        pronto = bool(pdf_unificado_scratch)
        if pronto:
            mensagem = (
                f'Geração institucional concluída ({titulo}). '
                'PDF, CSV e ZIP salvos na pasta de saída.'
            )
        else:
            mensagem = (
                f'CSV e ZIP salvos ({titulo}); PDF unificado pendente — '
                f'{mensagem_pdf or "ver layout/LEIA-ME_LAYOUTS.txt"}'
            )
        _log(messages, mensagem)
        return _resultado(
            pronto,
            mensagem,
            pdf=artefatos.get('pdf', ''),
            csv=artefatos.get('csv', ''),
            zip_=artefatos.get('zip', ''),
        )
