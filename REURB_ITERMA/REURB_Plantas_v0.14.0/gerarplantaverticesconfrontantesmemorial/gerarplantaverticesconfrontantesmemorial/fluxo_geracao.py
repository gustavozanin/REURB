# -*- coding: utf-8 -*-
"""Fluxo de geração da planta Vértices / Confrontantes / Memorial (Desktop).

`executar_geracao_memorial` liga ponta a ponta (espelhando
`gerarplantanucleo/gerarplantanucleo/fluxo_geracao.py`, mas sem
lotes/quadras e com UTM/memorial/quadro em vez de anexo de quadras):

    1. `caminho_camadas.inicializar_caminhos` (modo FEATURESERVER)
    2. `check_reurb_coletivo` / `check_status` / `check_responsavel_tecnico`
    3. `exporta_shapefile` -> bairro selecionado (já em UTM), fuso, área, perímetro
    4. `municipalidade` -> município do bairro
    5. `pipeline_perimetro.montar_tabela_segmentos_de_vertices` ->
       vértices (com densidade `integral`/`simplificado` já aplicada,
       azimute/E/N em UTM) + tabela final de segmentos (de/para/azimute/
       distancia/E/N/confrontantes)
    6. `formatar_dados_perimetro` -> lista de dicts para CSV e memorial
    7. `quadro_coordenadas.exportar_csv` -> CSV (sempre, se a geometria rodou)
    8. `memorial_narrativo.gerar_texto_memorial` -> texto narrativo
    9. `exporta_shapefile.exportar_camadas_do_perimetro` +
       `zipar_shapefile` -> ZIP com bairro, vértices e segmentos, todos em UTM
    10. `gerar_planta_perimetro` + `memorial_narrativo.preencher_layout_memorial`
        + `quadro_coordenadas.preencher_layout_quadro` +
        `exportar_pdf_unificado.exportar_pacote_final` -> PDF unificado
        (a planta usa o layout A3 do APRX; memorial, quadro e termo são
        gerados via ReportLab; configuração incompleta do A3 é refletida
        no JSON)
    11. `salvar_artefatos_desktop.salvar_artefatos_memorial` -> cópia
        final para a pasta do analista

Regra de `pronto` (specs da Fase 3, mais restritiva que o Núcleo): CSV e
ZIP são copiados para a pasta de saída sempre que a geometria roda com
sucesso, independente do PDF. O PDF só é gerado quando o layout A3 atende
ao contrato obrigatório. `pronto=True` exige os três artefatos (PDF+CSV+ZIP);
com configuração pendente, a ferramenta ainda assim entrega CSV+ZIP e
`pronto=False` com mensagem apontando para `layout/LEIA-ME_LAYOUTS.txt`.

Falhas nos checks (REURB inexistente, bairro em andamento, RT não
cadastrado) interrompem antes de tocar em geometria/artefatos, iguais ao
Núcleo — nenhum arquivo é copiado para a pasta de saída nesses casos.
"""

import json
import os
from datetime import datetime

import arcpy

import caminho_camadas as _caminho_camadas
from simplificar_vertices import simplificar_anel
from check_reurb_coletivo import check_reurb_coletivo
from check_status import check_status
from check_responsavel import check_responsavel_tecnico
from exporta_shapefile import (
    exportar_camadas_do_perimetro,
    exporta_shapefile,
    zipar_shapefile,
)
from municipalidade import municipalidade
from formatar_dados_perimetro import formatar_dados_perimetro
from quadro_coordenadas import (
    exportar_csv as exportar_csv_quadro,
    preencher_layout_quadro,
    NOME_LAYOUT_QUADRO,
)
from memorial_narrativo import (
    gerar_texto_memorial,
    preencher_layout_memorial,
    NOME_LAYOUT_MEMORIAL,
)
from gerar_planta_perimetro import (
    LayoutConfigurationError,
    gerar_planta_perimetro,
    exportar_planta_perimetro_para_pdf,
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


def _abrir_layout(aprx, nome):
    """Busca um layout pelo nome num `arcpy.mp.ArcGISProject` já aberto.

    Reaproveita o mesmo `aprx` aberto por `gerar_planta_perimetro` (que já
    validou a existência do `.aprx`) para buscar os layouts Memorial e
    Quadro, evitando abrir o projeto três vezes.

    Raises:
        LayoutConfigurationError: configuração obrigatória ausente no APRX.
    """
    for layout in aprx.listLayouts():
        if layout.name == nome:
            return layout
    raise RuntimeError(
        f'Layout "{nome}" não encontrado no project_layout.aprx desta '
        f'ferramenta. Crie os layouts no ArcGIS Pro conforme '
        f'layout/LEIA-ME_LAYOUTS.txt antes de gerar o PDF unificado.'
    )


def aplicar_densidade_vertices(fc_vertices, densidade, tolerancia_m=0.5, messages=None):
    """
    Aplica o parâmetro de densidade à feição de pontos do perímetro
    (saída de `transforma_feicao.transforma_feicao`: anel fechado, ordem
    do polígono, último ponto repete o primeiro).

    - `integral`: retorna a própria feição recebida, sem alterações.
    - `simplificado`: lê os pontos em ordem (OID), aplica
      `simplificar_vertices.simplificar_anel` e reescreve uma nova
      feição de pontos (no scratchGDB) só com o anel simplificado.

    Args:
        fc_vertices: caminho da feição de pontos do anel.
        densidade: 'integral' ou 'simplificado'.
        tolerancia_m: tolerância (m) da simplificação colinear; usada
            apenas quando densidade='simplificado'.
        messages: objeto de mensagens da toolbox (opcional).

    Returns:
        os.PathLike: caminho da feição de pontos a usar no restante do
        pipeline — a mesma recebida (`integral`) ou uma nova
        (`simplificado`).

    Raises:
        ValueError: densidade inválida, ou simplificação inviável
            (ver `simplificar_vertices.simplificar_anel`).
    """
    densidade = (densidade or 'integral').strip().lower()
    if densidade not in DENSIDADES_VALIDAS:
        raise ValueError(
            f'Densidade inválida: "{densidade}". '
            f'Valores aceitos: {", ".join(DENSIDADES_VALIDAS)}.'
        )

    if densidade == 'integral':
        _log(messages, 'Densidade "integral": mantendo todos os vértices do anel.')
        return fc_vertices

    with arcpy.da.SearchCursor(fc_vertices, ['OID@', 'SHAPE@X', 'SHAPE@Y']) as cursor:
        pontos_ordenados = sorted(cursor, key=lambda linha: linha[0])
    pontos_xy = [(x, y) for _oid, x, y in pontos_ordenados]

    pontos_simplificados = simplificar_anel(pontos_xy, tolerancia_m=tolerancia_m)

    desc = arcpy.Describe(fc_vertices)
    sr = desc.spatialReference
    out_name = 'vertices_simplificados'
    out_fc = os.path.join(arcpy.env.scratchGDB, out_name)
    if arcpy.Exists(out_fc):
        arcpy.Delete_management(out_fc)

    arcpy.management.CreateFeatureclass(
        out_path=arcpy.env.scratchGDB,
        out_name=out_name,
        geometry_type='POINT',
        spatial_reference=sr,
    )
    with arcpy.da.InsertCursor(out_fc, ['SHAPE@XY']) as icursor:
        for x, y in pontos_simplificados:
            icursor.insertRow([(x, y)])

    _log(
        messages,
        f'Densidade "simplificado" (tolerância {tolerancia_m} m): '
        f'{len(pontos_xy)} -> {len(pontos_simplificados)} vértices.',
    )
    return out_fc


def executar_geracao_memorial(
    numero_reurb_coletivo,
    pasta_saida=None,
    messages=None,
    featureserver_url=None,
    nome_override=None,
    formacao_override=None,
    credenciamento_override=None,
    densidade='integral',
    tolerancia_m=0.5,
):
    """
    Executa o fluxo completo de geração do memorial descritivo (Desktop,
    via FeatureServer): checks -> geometria UTM -> confrontantes ->
    CSV/memorial/ZIP -> PDF unificado (se os layouts já existirem) ->
    cópia final para `pasta_saida`.

    Args:
        numero_reurb_coletivo: número do processo coletivo.
        pasta_saida: pasta onde o PDF/CSV/ZIP finais serão salvos.
        messages: objeto com AddMessage/AddError (toolbox).
        featureserver_url: URL base do FeatureServer (avançado).
        nome_override / formacao_override / credenciamento_override:
            overrides opcionais do responsável técnico (igual ao Núcleo).
        densidade: 'integral' ou 'simplificado'.
        tolerancia_m: tolerância (m) da simplificação colinear (avançado).

    Returns:
        str: JSON com `pronto`, `numeroProcessoColetivo`, `densidade`,
        `toleranciaM`, `pdf`, `csv`, `zip` e `mensagem`. `pronto=True`
        somente quando PDF, CSV e ZIP foram todos gerados e copiados
        para `pasta_saida`; com configuração do A3 pendente, CSV e ZIP ainda assim
        são copiados (se a geometria rodou) e `pronto=False` explica o
        motivo do PDF pendente.
    """
    numero_reurb_coletivo = (numero_reurb_coletivo or '').strip()
    densidade = (densidade or 'integral').strip().lower()

    erros = []
    if not numero_reurb_coletivo:
        erros.append('Número do REURB coletivo não informado.')

    if not pasta_saida:
        erros.append('Pasta de saída não informada.')
    elif not os.path.isdir(pasta_saida):
        erros.append(f'Pasta de saída não encontrada: {pasta_saida}')

    if densidade not in DENSIDADES_VALIDAS:
        erros.append(
            f'Densidade inválida: "{densidade}". '
            f'Valores aceitos: {", ".join(DENSIDADES_VALIDAS)}.'
        )

    try:
        tolerancia_m = float(tolerancia_m)
        if tolerancia_m <= 0:
            erros.append('Tolerância (m) deve ser maior que zero.')
    except (TypeError, ValueError):
        erros.append(f'Tolerância (m) inválida: "{tolerancia_m}".')
        tolerancia_m = None

    def _resultado(pronto, mensagem, pdf='', csv='', zip_=''):
        return json.dumps(
            {
                'pronto': pronto,
                'numeroProcessoColetivo': numero_reurb_coletivo,
                'densidade': densidade,
                'toleranciaM': tolerancia_m,
                'pdf': pdf,
                'csv': csv,
                'zip': zip_,
                'mensagem': mensagem,
            },
            ensure_ascii=False,
        )

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
    eixo_viario_camada = _caminho_camadas.eixo_viario_camada
    confrontante_camada = _caminho_camadas.confrontante_camada
    responsavel_tecnico_tabela = _caminho_camadas.responsavel_tecnico_tabela
    municipios_camada = _caminho_camadas.municipios_camada

    if None in [
        bairro_camada,
        eixo_viario_camada,
        confrontante_camada,
        responsavel_tecnico_tabela,
        municipios_camada,
    ]:
        raise ValueError('Caminhos não inicializados corretamente')

    scratchgdb = arcpy.env.scratchGDB
    scratch_folder = arcpy.env.scratchFolder

    with arcpy.EnvManager(workspace=scratchgdb, overwriteOutput=True):
        _log(messages, 'Início - Verificando se o número do REURB coletivo existe')
        if check_reurb_coletivo(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        ) is False:
            return _resultado(False, 'Número do REURB coletivo inexistente.')
        _log(messages, 'Fim - Verificando se o número do REURB coletivo existe')

        _log(messages, 'Início - Verificando se o bairro está pronto')
        if check_status(
            feicao_bairro=bairro_camada,
            numero_reurb_coletivo=numero_reurb_coletivo,
        ) is False:
            return _resultado(
                False, 'Bairro em andamento (status diferente de 2 ou 4).'
            )
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
                f'Responsável técnico "{responsavel_tecnico}" não cadastrado '
                f'ou preenchimento incorreto',
            )
            return _resultado(
                False,
                f'Responsável técnico "{responsavel_tecnico}" não cadastrado '
                f'ou preenchimento incorreto. Informe formação e CREA/CAU na '
                f'ferramenta Desktop.',
            )
        _log(messages, 'Fim - Verificando se o responsável técnico existe')

        _log(messages, 'Início - Exportando bairro, fuso UTM, área e perímetro')
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
        _municipios, municipio_principal = municipalidade(
            feicao_perimetro=bairro_selecionado,
            municipios=municipios_camada,
            area=area_bairro,
        )
        _log(messages, 'Fim - Selecionando município')

        meta = {
            'numero_reurb': numero_reurb_coletivo,
            'bairro': bairro,
            'municipio': municipio_principal.get('nome'),
            'uf': UF_PADRAO,
            'area_m2': area_bairro,
            'perimetro_m': perimetro_bairro,
            'fuso': codigo_fuso_bairro,
            'meridiano_central': meridiano_central,
            'densidade': densidade,
            'rt_nome': responsavel_tecnico,
            'rt_formacao': formacao,
            'rt_crea': codigo_credenciamento,
        }

        _log(
            messages,
            'Início - Calculando vértices (densidade), azimute UTM, '
            'segmentos e confrontantes',
        )
        import pipeline_perimetro

        tabela_final, vertices_bairro, auditoria_geometrica = pipeline_perimetro.montar_tabela_segmentos_de_vertices(
            feicao_perimetro=bairro_selecionado,
            n_coletivo=numero_reurb_coletivo,
            bairro_feicoes=bairro_camada,
            confrontante_feicoes=confrontante_camada,
            eixo_viario=eixo_viario_camada,
            densidade=densidade,
            tolerancia_m=tolerancia_m,
            messages=messages,
        )
        _log(
            messages,
            'Fim - Calculando vértices, azimute UTM, segmentos e confrontantes',
        )

        _log(messages, 'Início - Formatando dados do perímetro (CSV/memorial)')
        area_bairro, perimetro_bairro = _sincronizar_medidas_perimetro(
            bairro_selecionado, auditoria_geometrica, meta, messages
        )
        _log(
            messages,
            'Área e perímetro sincronizados com a poligonal descrita: '
            f'{area_bairro:.2f} m²; {perimetro_bairro:.2f} m',
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
        _log(messages, 'Fim - Formatando dados do perímetro')

        slug = numero_reurb_coletivo.replace('/', '_')

        _log(messages, 'Início - Exportando CSV do quadro de coordenadas')
        csv_scratch = os.path.join(scratch_folder, f'quadro_coordenadas_{slug}.csv')
        exportar_csv_quadro(dados_perimetro, csv_scratch)
        _log(messages, 'Fim - Exportando CSV do quadro de coordenadas')

        _log(messages, 'Início - Gerando texto do memorial narrativo')
        texto_memorial = gerar_texto_memorial(dados_perimetro, meta=meta)
        _log(messages, 'Fim - Gerando texto do memorial narrativo')

        _log(messages, 'Início - Zipando shapefile')
        exportar_camadas_do_perimetro(
            dir_shapefile=dir_shapefile,
            numero_reurb_coletivo=numero_reurb_coletivo,
            vertices=vertices_bairro,
            segmentos=tabela_final,
        )
        zip_scratch = zipar_shapefile(dir_shapefile=dir_shapefile)
        _log(messages, 'Fim - Zipando shapefile')

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

        plano_folhas = planejar_folhas(len(dados_perimetro))
        if plano_folhas['tem_anexo']:
            _log(
                messages,
                f'{len(dados_perimetro)} segmentos: Quadro de Confrontações '
                f"vai como folha adicional (Folha {plano_folhas['folha_quadro']})",
            )
        else:
            _log(
                messages,
                f'{len(dados_perimetro)} segmentos: lista completa cabe na '
                'planta (folha única, sem quadro em anexo)',
            )

        pdf_unificado_scratch = None
        mensagem_pdf = None
        _log(
            messages,
            'Início - Gerando PDF unificado (planta + quadro + memorial + termo)',
        )
        try:
            data_planta = datetime.now().strftime('%d/%m/%Y')
            layout_planta, aprx = gerar_planta_perimetro(
                bairro_selecionado=bairro_selecionado,
                confrontantes_bairro=tabela_final,
                vertices_bairro=vertices_bairro,
                bairro=bairro,
                municipio=municipio_principal.get('nome'),
                area=area_bairro,
                processo=numero_reurb_coletivo,
                perimetro=perimetro_bairro,
                data=data_planta,
                fusoutm=codigo_fuso_bairro,
                responsavel_tecnico=responsavel_tecnico,
                funcao=formacao,
                n_crea_cau=codigo_credenciamento,
                total_segmentos=len(dados_perimetro),
                protocolo=selo['protocolo'],
            )
            pdf_planta = exportar_planta_perimetro_para_pdf(
                layout_planta, os.path.join(scratch_folder, 'planta_perimetro.pdf')
            )

            pdf_quadro = None
            if plano_folhas['tem_anexo']:
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
                scratch_folder, f'planta_vertices_memorial_{slug}.pdf'
            )
            exportar_pacote_final(
                pdf_planta,
                pdf_quadro,
                pdf_memorial,
                pdf_unificado_scratch,
                termo=pdf_termo,
            )
            _log(messages, 'Fim - Gerando PDF unificado')
        except LayoutConfigurationError as e:
            mensagem_pdf = str(e)
            pdf_unificado_scratch = None
            _log(messages, f'PDF unificado pendente (layout): {mensagem_pdf}')
        except RuntimeError as e:
            # Rede de segurança: sem ela, uma falha operacional derruba a
            # ferramenta e o analista perde também o CSV e o ZIP.
            mensagem_pdf = str(e)
            pdf_unificado_scratch = None
            _log(messages, f'PDF unificado pendente: {mensagem_pdf}')

        _log(messages, 'Início - Salvando artefatos na pasta de saída')
        artefatos = salvar_artefatos_memorial(
            pasta_saida=pasta_saida,
            numero_reurb_coletivo=numero_reurb_coletivo,
            pdf_unificado=pdf_unificado_scratch,
            csv_quadro=csv_scratch,
            zip_shapefile=zip_scratch,
        )
        auditoria_path = os.path.join(
            pasta_saida, f'validacao_geometrica_{slug}.json'
        )
        auditoria_geometrica.update({
            'numeroProcessoColetivo': numero_reurb_coletivo,
            'densidadeSolicitada': densidade,
            'densidadeAplicada': densidade,
            'geradoEm': datetime.now().isoformat(timespec='seconds'),
            'protocoloEmissao': selo['protocolo'],
            'hashConteudo': selo['hash_conteudo'],
            'hashesArquivos': selo['hashes_arquivos'],
        })
        with open(auditoria_path, 'w', encoding='utf-8') as arquivo:
            json.dump(auditoria_geometrica, arquivo, ensure_ascii=False, indent=2)
        _log(messages, f'Auditoria geométrica salva em: {auditoria_path}')
        _log(messages, 'Fim - Salvando artefatos na pasta de saída')

        pronto = bool(pdf_unificado_scratch)
        if pronto:
            mensagem = (
                'Geração concluída. PDF, CSV e ZIP salvos na pasta de saída.'
            )
        else:
            mensagem = (
                'CSV e ZIP salvos na pasta de saída; PDF unificado pendente — '
                f'{mensagem_pdf}'
            )

        return _resultado(
            pronto,
            mensagem,
            pdf=artefatos.get('pdf', ''),
            csv=artefatos.get('csv', ''),
            zip_=artefatos.get('zip', ''),
        )
