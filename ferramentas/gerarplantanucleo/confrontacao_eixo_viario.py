# -*- coding: utf-8 -*-

import os
import uuid
import math

import arcpy


EIXO_VIARIO_LOCAL = r"C:\REURB\SHP\eixo_viario_Peri Mirim.shp"
FEATURESERVER_REURB_ITERMA = "https://www.arcgis.iterma.ma.gov.br/server/rest/services/CAMADAS_ITERMA/REURB_ITERMA/FeatureServer"
EIXO_VIARIO_FEATURE_SERVICE = f"{FEATURESERVER_REURB_ITERMA}/0"
PREFERIR_FEATURESERVER = True
TOLERANCIA_CONFRONTANTE_METROS = 30
TOLERANCIA_ROTULO_METROS = 35
AFASTAMENTO_ROTULO_CONFRONTANTE_METROS = 18
TOLERANCIA_TRANSFERENCIA_CONFRONTANTE_METROS = 35


def obter_eixo_viario():
    if PREFERIR_FEATURESERVER:
        try:
            if arcpy.Exists(EIXO_VIARIO_FEATURE_SERVICE):
                campo_logradouro = _campo_logradouro(EIXO_VIARIO_FEATURE_SERVICE)
                if campo_logradouro:
                    arcpy.AddMessage(f"✓ Usando eixo viario do FeatureServer: {EIXO_VIARIO_FEATURE_SERVICE}")
                    return EIXO_VIARIO_FEATURE_SERVICE
                arcpy.AddWarning("Campo logradouro nao encontrado no FeatureServer de eixo viario.")
            else:
                arcpy.AddWarning(f"FeatureServer de eixo viario nao acessivel: {EIXO_VIARIO_FEATURE_SERVICE}")
        except Exception as e:
            arcpy.AddWarning(f"Nao foi possivel consultar o FeatureServer de eixo viario: {str(e)}")

    if os.path.exists(EIXO_VIARIO_LOCAL):
        arcpy.AddMessage(f"✓ Usando eixo viario local: {EIXO_VIARIO_LOCAL}")
        return EIXO_VIARIO_LOCAL
    return None


def _campo_logradouro(eixo_viario):
    campos = {field.name.lower(): field.name for field in arcpy.ListFields(eixo_viario)}
    return campos.get('logradouro')


def filtrar_eixo_confrontante(feicao_perimetro, eixo_viario=None, tolerancia=TOLERANCIA_ROTULO_METROS):
    eixo_viario = eixo_viario or obter_eixo_viario()
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        arcpy.AddWarning("Eixo viario nao encontrado para filtro de confrontacao.")
        return None

    campo_logradouro = _campo_logradouro(eixo_viario)
    if not campo_logradouro:
        arcpy.AddWarning("Campo logradouro nao encontrado no eixo viario.")
        return None

    try:
        buffer_perimetro = arcpy.Buffer_analysis(
            in_features=feicao_perimetro,
            out_feature_class=arcpy.CreateUniqueName('buffer_eixo_confrontante', arcpy.env.scratchGDB),
            buffer_distance_or_field=f'{tolerancia} Meters',
            line_side='FULL',
            line_end_type='ROUND',
            dissolve_option='ALL'
        )

        eixo_clip = arcpy.PairwiseClip_analysis(
            in_features=eixo_viario,
            clip_features=buffer_perimetro,
            out_feature_class=arcpy.CreateUniqueName('eixo_viario_confrontante', arcpy.env.scratchGDB)
        )

        quantidade = int(arcpy.management.GetCount(eixo_clip)[0])
        if quantidade == 0:
            arcpy.AddWarning("Nenhum eixo viario confrontante encontrado no buffer do perimetro.")
            return None

        try:
            eixo_dissolvido = arcpy.Dissolve_management(
                in_features=eixo_clip,
                out_feature_class=arcpy.CreateUniqueName('eixo_viario_confrontante_diss', arcpy.env.scratchGDB),
                dissolve_field=[campo_logradouro],
                multi_part='SINGLE_PART',
                unsplit_lines='DISSOLVE_LINES'
            )
            eixo_clip = eixo_dissolvido
        except Exception as e:
            arcpy.AddWarning(f"Nao foi possivel dissolver eixo por logradouro: {str(e)}")

        arcpy.AddMessage(f"Eixos viarios confrontantes filtrados: {int(arcpy.management.GetCount(eixo_clip)[0])}")
        return eixo_clip
    except Exception as e:
        arcpy.AddWarning(f"Nao foi possivel filtrar eixo viario confrontante: {str(e)}")
        return None


def preencher_confrontantes_por_eixo(confrontantes_bairro, eixo_viario=None, tolerancia=TOLERANCIA_CONFRONTANTE_METROS):
    eixo_viario = eixo_viario or obter_eixo_viario()
    if not eixo_viario or not arcpy.Exists(eixo_viario):
        arcpy.AddWarning("Eixo viario nao encontrado. Confrontantes por logradouro nao serao preenchidos.")
        return confrontantes_bairro

    campo_logradouro = _campo_logradouro(eixo_viario)
    if not campo_logradouro:
        arcpy.AddWarning("Campo logradouro nao encontrado no eixo viario.")
        return confrontantes_bairro

    sr_segmentos = arcpy.Describe(confrontantes_bairro).spatialReference
    eixos = []
    with arcpy.da.SearchCursor(eixo_viario, ['SHAPE@', campo_logradouro]) as cursor:
        for geom, logradouro in cursor:
            if not geom or not logradouro:
                continue
            try:
                geom = geom.projectAs(sr_segmentos)
            except Exception:
                pass
            eixos.append((geom, str(logradouro).strip()))

    if not eixos:
        arcpy.AddWarning("Nenhum eixo viario valido encontrado para confrontacao.")
        return confrontantes_bairro

    atualizados = 0
    with arcpy.da.UpdateCursor(confrontantes_bairro, ['SHAPE@', 'confrontantes']) as cursor:
        for row in cursor:
            if str(row[1] or '').strip():
                continue

            segmento = row[0]
            melhor_nome = ''
            melhor_distancia = None

            for eixo, logradouro in eixos:
                distancia = segmento.distanceTo(eixo)
                if melhor_distancia is None or distancia < melhor_distancia:
                    melhor_distancia = distancia
                    melhor_nome = logradouro

            if melhor_distancia is not None and melhor_distancia <= tolerancia:
                row[1] = melhor_nome
                cursor.updateRow(row)
                atualizados += 1

    preenchidos = 0
    nomes = set()
    with arcpy.da.SearchCursor(confrontantes_bairro, ['confrontantes']) as cursor:
        for row in cursor:
            nome = _nome_limpo(row[0])
            if nome:
                preenchidos += 1
                nomes.add(nome)

    arcpy.AddMessage(f"Confrontantes preenchidos pelo eixo viario: {atualizados}")
    arcpy.AddMessage(
        f"Resumo de confrontantes: {preenchidos} segmentos com confrontante; "
        f"{len(nomes)} nomes: {', '.join(sorted(nomes)[:12])}"
    )
    return confrontantes_bairro


def transferir_confrontantes_por_segmentos(
    confrontantes_destino,
    confrontantes_referencia,
    tolerancia=TOLERANCIA_TRANSFERENCIA_CONFRONTANTE_METROS
):
    campos_destino = {field.name for field in arcpy.ListFields(confrontantes_destino)}
    campos_referencia = {field.name for field in arcpy.ListFields(confrontantes_referencia)}
    if 'confrontantes' not in campos_destino or 'confrontantes' not in campos_referencia:
        arcpy.AddWarning("Campo confrontantes ausente para transferencia entre segmentos.")
        return confrontantes_destino

    sr_destino = arcpy.Describe(confrontantes_destino).spatialReference
    referencias = []
    with arcpy.da.SearchCursor(confrontantes_referencia, ['SHAPE@', 'confrontantes']) as cursor:
        for geom, nome in cursor:
            nome = _nome_limpo(nome)
            if not geom or not nome:
                continue
            try:
                geom = geom.projectAs(sr_destino)
            except Exception:
                pass
            try:
                ponto_medio = geom.positionAlongLine(0.5, True)
            except Exception:
                ponto_medio = geom.centroid
            referencias.append({
                'geom': geom,
                'nome': nome,
                'ponto_medio': ponto_medio,
                'peso': max(float(getattr(geom, 'length', 0) or 0), 0.01)
            })

    if not referencias:
        arcpy.AddWarning("Sem confrontantes de referencia para transferir para a planta simplificada.")
        return confrontantes_destino

    atualizados = 0
    with arcpy.da.UpdateCursor(confrontantes_destino, ['SHAPE@', 'confrontantes']) as cursor:
        for row in cursor:
            if str(row[1] or '').strip():
                continue

            segmento = row[0]
            if not segmento:
                continue

            pontuacao = {}
            for ref in referencias:
                try:
                    distancia = min(
                        segmento.distanceTo(ref['geom']),
                        ref['ponto_medio'].distanceTo(segmento)
                    )
                except Exception:
                    continue

                if distancia <= tolerancia:
                    pontuacao[ref['nome']] = pontuacao.get(ref['nome'], 0) + (ref['peso'] / (1 + distancia))

            if not pontuacao:
                continue

            melhor_nome = max(pontuacao.items(), key=lambda item: item[1])[0]
            row[1] = melhor_nome
            cursor.updateRow(row)
            atualizados += 1

    arcpy.AddMessage(f"Confrontantes transferidos para segmentos simplificados: {atualizados}")
    return confrontantes_destino


def _nome_limpo(valor):
    return str(valor or '').strip()


def _normalizar_nome(valor):
    return _nome_limpo(valor).upper()


def _agrupar_trechos_consecutivos(linhas):
    grupos = []
    grupo_atual = []
    nome_atual = None

    for linha in linhas:
        nome = _normalizar_nome(linha['confrontante'])
        if not nome:
            if grupo_atual:
                grupos.append(grupo_atual)
                grupo_atual = []
                nome_atual = None
            continue

        if nome_atual is None or nome == nome_atual:
            grupo_atual.append(linha)
            nome_atual = nome
        else:
            if grupo_atual:
                grupos.append(grupo_atual)
            grupo_atual = [linha]
            nome_atual = nome

    if grupo_atual:
        grupos.append(grupo_atual)

    return grupos


def _angulo_linha(geom):
    try:
        p_ini = geom.firstPoint
        p_fim = geom.lastPoint
        angulo = math.degrees(math.atan2(p_fim.Y - p_ini.Y, p_fim.X - p_ini.X))
        if angulo > 90:
            angulo -= 180
        elif angulo < -90:
            angulo += 180
        return angulo
    except Exception:
        return 0


def _ponto_rotulo_trecho(geometrias):
    comprimento_total = sum(max(geom.length, 0) for geom in geometrias)
    if not geometrias:
        return None, None

    alvo = comprimento_total / 2
    acumulado = 0
    for geom in geometrias:
        proximo = acumulado + geom.length
        if proximo >= alvo:
            fracao = 0.5 if geom.length == 0 else max(0, min(1, (alvo - acumulado) / geom.length))
            try:
                return geom.positionAlongLine(fracao, True), geom
            except Exception:
                return geom.centroid, geom
        acumulado = proximo

    return geometrias[-1].centroid, geometrias[-1]


def _afastar_ponto_para_fora(ponto, centro_x, centro_y, sr):
    ponto_base = ponto.firstPoint if hasattr(ponto, 'firstPoint') else ponto
    dx = ponto_base.X - centro_x
    dy = ponto_base.Y - centro_y
    norma = math.hypot(dx, dy)
    if not norma:
        return arcpy.PointGeometry(ponto_base, sr)

    ponto_afastado = arcpy.Point(
        ponto_base.X + (dx / norma) * AFASTAMENTO_ROTULO_CONFRONTANTE_METROS,
        ponto_base.Y + (dy / norma) * AFASTAMENTO_ROTULO_CONFRONTANTE_METROS
    )
    return arcpy.PointGeometry(ponto_afastado, sr)


def criar_rotulos_confrontantes(confrontantes_bairro):
    campos = {field.name for field in arcpy.ListFields(confrontantes_bairro)}
    if 'confrontantes' not in campos:
        return None

    sr = arcpy.Describe(confrontantes_bairro).spatialReference
    linhas = []
    pontos_referencia = []
    campos_cursor = ['OID@', 'SHAPE@', 'confrontantes', 'de', 'para']
    with arcpy.da.SearchCursor(confrontantes_bairro, campos_cursor) as cursor:
        for oid, geom, confrontante, de, para in cursor:
            if not geom or not confrontante:
                continue
            try:
                pontos_referencia.append(geom.positionAlongLine(0.5, True).firstPoint)
            except Exception:
                pontos_referencia.append(geom.centroid)
            nome = str(confrontante).strip()
            if not nome:
                continue
            linhas.append({
                'oid': oid,
                'geom': geom,
                'confrontante': nome,
                'de': de,
                'para': para
            })

    if not linhas:
        arcpy.AddWarning("Nenhum confrontante preenchido para rotular na planta.")
        return None

    centro_x = sum(ponto.X for ponto in pontos_referencia) / len(pontos_referencia)
    centro_y = sum(ponto.Y for ponto in pontos_referencia) / len(pontos_referencia)
    grupos = _agrupar_trechos_consecutivos(linhas)

    rotulos = arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.scratchGDB,
        out_name=f'rotulos_confrontantes_{uuid.uuid4().hex[:8]}',
        geometry_type='POINT',
        spatial_reference=sr,
        has_m='DISABLED',
        has_z='DISABLED'
    )
    arcpy.AddField_management(rotulos, 'logradouro', 'TEXT', field_length=120)
    arcpy.AddField_management(rotulos, 'label_txt', 'TEXT', field_length=120)
    arcpy.AddField_management(rotulos, 'angulo', 'DOUBLE')

    with arcpy.da.InsertCursor(rotulos, ['SHAPE@', 'logradouro', 'label_txt', 'angulo']) as insert_cursor:
        for grupo in grupos:
            geometrias = [item['geom'] for item in grupo]
            ponto, geom_rotulo = _ponto_rotulo_trecho(geometrias)
            if ponto is None:
                continue

            nome = _nome_limpo(grupo[0]['confrontante'])
            de = grupo[0].get('de') or ''
            para = grupo[-1].get('para') or ''
            intervalo = f'{de}-{para}'.strip('-')
            if intervalo:
                label_txt = f'{intervalo} {nome}'
            else:
                label_txt = nome

            ponto = _afastar_ponto_para_fora(ponto, centro_x, centro_y, sr)
            insert_cursor.insertRow([ponto, nome, label_txt, 0])

    nomes_grupos = sorted({_nome_limpo(grupo[0]['confrontante']) for grupo in grupos if grupo})
    arcpy.AddMessage(
        f"Rotulos de confrontantes criados por trecho para a planta: {len(grupos)}; "
        f"nomes: {', '.join(nomes_grupos[:12])}"
    )
    return rotulos
