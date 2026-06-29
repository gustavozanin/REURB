# -*- coding: utf-8 -*-

import importlib.util
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path


BASE_LOCAL = Path(__file__).parent
BASE_FERRAMENTAS = BASE_LOCAL.parent
BASE_LOTEAMENTO = BASE_FERRAMENTAS / "gerarpranchaloteamento"
APRX_PADRAO = r"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx"


def _carregar_motor_loteamento():
    if str(BASE_LOTEAMENTO) not in sys.path:
        sys.path.insert(0, str(BASE_LOTEAMENTO))

    nome_modulo = "_motor_prancha_loteamento_arcgis"
    if nome_modulo in sys.modules:
        motor = sys.modules[nome_modulo]
    else:
        caminho = BASE_LOTEAMENTO / "gerar_prancha_loteamento_arcgis.py"
        spec = importlib.util.spec_from_file_location(nome_modulo, str(caminho))
        motor = importlib.util.module_from_spec(spec)
        sys.modules[nome_modulo] = motor
        spec.loader.exec_module(motor)

    motor.projeto_arcgis = str(BASE_LOCAL / "layout" / "project_layout.aprx")
    motor.SIMBOLOGIA_PERIMETRO_OVERVIEW = BASE_LOCAL / "layers" / "PERIMETRO_OVERVIEW.lyrx"
    return motor


def slug_resultado(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "_", texto).strip("_")
    return texto or "nucleo"


def _pasta_resultado(dados):
    numero = str(dados.get("numeroProcessoColetivo") or dados.get("n_coletivo") or "").replace("/", "_")
    bairro = slug_resultado(dados.get("bairro") or dados.get("nome") or "nucleo")
    nome = f"{bairro}_{numero}" if numero else bairro
    pasta = BASE_LOCAL / "resultados" / nome
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _normalizar_item(item):
    normalizado = dict(item or {})
    dados = dict(normalizado.get("dados") or {})

    numero = (
        dados.get("numeroProcessoColetivo")
        or dados.get("n_coletivo")
        or normalizado.get("numeroProcessoColetivo")
        or normalizado.get("n_coletivo")
    )
    bairro = dados.get("bairro") or dados.get("nome") or normalizado.get("bairro") or normalizado.get("nome")
    municipio = dados.get("municipio") or normalizado.get("municipio") or "Peri Mirim"

    dados["numeroProcessoColetivo"] = str(numero or "").replace("_", "/")
    dados["bairro"] = str(bairro or "").title()
    dados["municipio"] = municipio
    dados["etapa"] = dados.get("etapa") or normalizado.get("etapa") or "Pre-vetorizacao"
    dados["statusAndamento"] = dados.get("statusAndamento") or normalizado.get("statusAndamento") or "Pre vetorizacao em andamento"

    normalizado["dados"] = dados
    normalizado["resultado"] = "Prancha Andamento REURB"
    normalizado["exportarCamadasArcGIS"] = bool(normalizado.get("exportarCamadasArcGIS", True))
    normalizado["aprxCamadas"] = normalizado.get("aprxCamadas") or normalizado.get("camadas") or APRX_PADRAO
    normalizado["anexarLista"] = bool(normalizado.get("anexarLista", True))

    pasta = Path(normalizado.get("pastaSaida") or dados.get("pastaSaida") or _pasta_resultado(dados))
    pasta.mkdir(parents=True, exist_ok=True)
    normalizado["pastaSaida"] = str(pasta)
    dados["pastaSaida"] = str(pasta)
    return normalizado


def _renomear_saida_pdf(resultado, item):
    if not isinstance(resultado, str):
        return resultado
    origem = Path(resultado)
    if not origem.exists():
        return resultado
    dados = item.get("dados") or {}
    municipio = slug_resultado(dados.get("municipio") or "municipio").upper()
    bairro = slug_resultado(dados.get("bairro") or "bairro").upper()
    numero = slug_resultado(dados.get("numeroProcessoColetivo") or "processo").upper()
    destino = origem.parent / f"PRANCHA_ANDAMENTO_REURB_{municipio}_{bairro}_{numero}_ARCGIS.pdf"
    if origem.resolve() != destino.resolve():
        shutil.copy2(str(origem), str(destino))
    return str(destino)


def _instalar_textos_andamento(motor, item):
    if not hasattr(motor, "_atualizar_textos_padrao_original"):
        motor._atualizar_textos_padrao_original = getattr(motor, "_atualizar_textos_padrao")
    original = motor._atualizar_textos_padrao_original
    dados_item = item.get("dados") or {}
    etapa = dados_item.get("etapa") or "Pre-vetorizacao"
    status = dados_item.get("statusAndamento") or "Pre vetorizacao em andamento"

    def atualizar(layout, numero, municipio, bairro, total_lotes, total_beneficiarios, escala, **kwargs):
        original(layout, numero, municipio, bairro, total_lotes, total_beneficiarios, escala, **kwargs)
        area = motor.decimal_texto(kwargs.get("area_bairro")) if kwargs.get("area_bairro") else ""
        perimetro = motor.decimal_texto(kwargs.get("perimetro_bairro")) if kwargs.get("perimetro_bairro") else ""
        titulo = f"PRANCHA ANDAMENTO REURB - {bairro.upper()}"
        motor._texto_existente(layout, "titulo_prancha_loteamento", titulo, x=13.1, y=27.35, tamanho=13, largura=18.0)
        motor._texto_existente(layout, "subtitulo_prancha_loteamento", etapa.upper(), x=13.1, y=26.95, tamanho=8, largura=18.0)
        motor._texto_existente(
            layout,
            "carimbo_prancha_loteamento",
            (
                "Legenda - Status dos Lotes\n"
                + "\n".join(f"{codigo} - {descricao}" for codigo, (descricao, _) in motor.STATUS_LEGENDA.items())
                + "\n\nDados da Prancha Andamento REURB\n"
                f"Municipio: {municipio}\n"
                f"Nucleo/Bairro: {bairro}\n"
                f"Processo coletivo: {numero}\n"
                f"Etapa: {etapa}\n"
                f"Status: {status}\n"
                f"Area do perimetro (m2): {area}\n"
                f"Perimetro (m): {perimetro}\n"
                f"Total de lotes: {total_lotes}\n"
                f"Beneficiarios listados: {total_beneficiarios}\n"
                "Sistema: SIRGAS 2000 / UTM 23S\n"
                f"Escala aproximada: 1:{escala}"
            ),
            x=21.8,
            y=24.2,
            tamanho=6.2,
            largura=14.8,
        )

    motor._atualizar_textos_padrao = atualizar


def ler_input_json(texto):
    if not texto:
        raise ValueError("inputJson vazio.")
    texto = str(texto).strip()
    if not texto.startswith("{") and not texto.startswith("["):
        caminho = Path(texto.strip("\"'"))
        if caminho.exists():
            texto = caminho.read_text(encoding="utf-8")
    if texto.startswith("'") and texto.endswith("'"):
        texto = texto[1:-1]
    entrada = json.loads(texto)
    if isinstance(entrada, dict) and "coletivos" in entrada:
        entrada = dict(entrada)
        entrada["coletivos"] = [_normalizar_item(item) for item in entrada.get("coletivos") or []]
        return entrada
    return _normalizar_item(entrada)


def executar_item(input_json):
    item = _normalizar_item(input_json)
    motor = _carregar_motor_loteamento()
    _instalar_textos_andamento(motor, item)
    resultado = motor.executar_por_json(item)
    return _renomear_saida_pdf(resultado, item)


def executar_por_json(input_json):
    entrada = input_json if isinstance(input_json, dict) else ler_input_json(input_json)
    if isinstance(entrada, dict) and "coletivos" in entrada:
        resultados = []
        for item in entrada.get("coletivos") or []:
            resultados.append({
                "dados": item.get("dados", {}),
                "pdf": executar_item(item),
                "pastaSaida": item.get("pastaSaida"),
            })
        return {
            "resultado": "Prancha Andamento REURB",
            "total": len(resultados),
            "resultados": resultados,
        }
    return executar_item(entrada)
