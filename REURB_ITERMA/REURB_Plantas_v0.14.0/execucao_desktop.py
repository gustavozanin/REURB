# -*- coding: utf-8 -*-
"""Isola cada corrida Desktop: versão, scratch, pasta e diário.

Não entra no sys.modules pelo nome curto `execucao_desktop`. A toolbox
carrega este arquivo com uma chave feita do caminho absoluto, para duas
versões do pacote não se misturarem no ArcGIS Pro.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime

_REURB_EXECUCAO_DESKTOP = True


def chave_modulo(caminho_arquivo: str, prefixo: str = "reurb_ed_") -> str:
    """Chave estável de sys.modules: caminho absoluto normalizado."""
    absoluto = os.path.normcase(
        os.path.normpath(os.path.abspath(caminho_arquivo))
    )
    digest = hashlib.md5(absoluto.encode("utf-8")).hexdigest()[:16]
    return prefixo + digest


def achar_raiz_pacote(partida: str) -> str:
    """Sobe pastas até achar VERSAO.txt ao lado deste helper."""
    raiz = os.path.dirname(os.path.abspath(partida))
    for _ in range(8):
        if os.path.isfile(os.path.join(raiz, "VERSAO.txt")):
            return raiz
        pai = os.path.dirname(raiz)
        if pai == raiz:
            break
        raiz = pai
    raise RuntimeError(
        "Não achei VERSAO.txt subindo a partir de: " + str(partida)
    )


def ler_versao(raiz: str) -> dict:
    """Lê VERSAO.txt (linhas chave=valor)."""
    caminho = os.path.join(raiz, "VERSAO.txt")
    dados = {"caminho": caminho, "versao": "desconhecida"}
    if not os.path.isfile(caminho):
        return dados
    with open(caminho, encoding="utf-8") as arquivo:
        for linha in arquivo:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            dados[chave.strip()] = valor.strip()
    return dados


def slug_processo(numero) -> str:
    bruto = str(numero or "sem_processo").strip() or "sem_processo"
    return bruto.replace("/", "_").replace("\\", "_")


def montar_pasta_execucao(
    pasta_usuario: str,
    ferramenta: str,
    numero,
    id_execucao: str,
) -> str:
    """Subpasta única: ferramenta_processo_data_pid."""
    nome = "{}_{}_{}".format(
        ferramenta,
        slug_processo(numero),
        id_execucao,
    )
    return os.path.join(pasta_usuario, nome)


def copiar_sem_sobrescrever(origem, destino) -> str:
    """Copia arquivo. Falha se o destino já existir."""
    if os.path.exists(destino):
        raise ValueError(
            "Já existe um arquivo neste caminho e a ferramenta não "
            "sobrescreve: {}".format(destino)
        )
    pasta = os.path.dirname(destino)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    shutil.copy2(origem, destino)
    return destino


def _info_pro() -> dict:
    info = {
        "python": sys.version.split()[0],
        "executavel": sys.executable,
    }
    try:
        import arcpy

        instalacao = arcpy.GetInstallInfo()
        info["produto"] = instalacao.get("ProductName")
        info["versao"] = instalacao.get("Version")
        info["build"] = instalacao.get("BuildNumber")
    except Exception as erro:
        info["aviso"] = str(erro)
    return info


def _modulos_caixa(raiz: str = None) -> list:
    """Lista só módulos desta pasta do pacote (ignora outra versão na sessão)."""
    itens = []
    ignorados = 0
    raiz_norm = ""
    if raiz:
        raiz_norm = os.path.normcase(os.path.normpath(os.path.abspath(raiz)))
    for nome in sorted(sys.modules):
        if not (
            nome.startswith("reurb_caixa_") or nome.startswith("reurb_ed_")
        ):
            continue
        modulo = sys.modules.get(nome)
        arquivo = getattr(modulo, "__file__", "") or ""
        if raiz_norm:
            arquivo_norm = os.path.normcase(
                os.path.normpath(os.path.abspath(arquivo))
            ) if arquivo else ""
            if not arquivo_norm.startswith(raiz_norm):
                ignorados += 1
                continue
        itens.append({"nome": nome, "arquivo": arquivo})
    return itens, ignorados


def _log(messages, texto: str) -> None:
    if messages is not None and hasattr(messages, "AddMessage"):
        messages.AddMessage(texto)
    else:
        try:
            import arcpy

            arcpy.AddMessage(texto)
        except Exception:
            print(texto)


def _contar(camada, where=None, nome_layer="diag_cnt") -> int:
    import arcpy

    if arcpy.Exists(nome_layer):
        arcpy.Delete_management(nome_layer)
    camada_lyr = arcpy.MakeFeatureLayer_management(
        in_features=camada,
        out_layer=nome_layer,
        where_clause=where,
    )
    try:
        return int(arcpy.management.GetCount(camada_lyr).getOutput(0))
    finally:
        if arcpy.Exists(nome_layer):
            arcpy.Delete_management(nome_layer)


def _contar_local(
    origem,
    where,
    bairro,
    overlap,
    nome_layer,
) -> int:
    import arcpy

    if arcpy.Exists(nome_layer):
        arcpy.Delete_management(nome_layer)
    camada_lyr = arcpy.MakeFeatureLayer_management(
        in_features=origem,
        out_layer=nome_layer,
        where_clause=where,
    )
    try:
        arcpy.SelectLayerByLocation_management(
            in_layer=camada_lyr,
            overlap_type=overlap,
            select_features=bairro,
            selection_type="NEW_SELECTION",
        )
        return int(arcpy.management.GetCount(camada_lyr).getOutput(0))
    finally:
        if arcpy.Exists(nome_layer):
            arcpy.Delete_management(nome_layer)


def _codigos_quadra(quadra_layout) -> list:
    import arcpy

    nomes = {f.name.lower(): f.name for f in arcpy.ListFields(quadra_layout)}
    campo = nomes.get("quadra")
    if not campo:
        return []
    vistos = []
    with arcpy.da.SearchCursor(quadra_layout, [campo]) as cursor:
        for (valor,) in cursor:
            texto = str(valor or "").strip()
            if texto and texto not in vistos:
                vistos.append(texto)
    return vistos


class ContextoExecucao:
    """Estado de uma corrida Desktop (scratch, pasta, diário)."""

    def __init__(self):
        self.id_execucao = ""
        self.ferramenta = ""
        self.numero_reurb = ""
        self.versao = {}
        self.pro = {}
        self.pasta_modulos = ""
        self.pasta_saida = ""
        self.scratch_dir = ""
        self.scratch_gdb = ""
        self.inicio = ""
        self.diagnostico = {}
        self.modulos = []
        self._ws_anterior = None
        self._restaurado = False

    def diagnosticar_selecao(
        self,
        numero_reurb_coletivo,
        quadra_origem,
        lote_origem,
        bairro_layout,
        quadra_layout,
        lote_layout,
        messages=None,
    ) -> dict:
        """Compara contagem por atributo, INTERSECT, centroide e layout."""
        texto = str(numero_reurb_coletivo).replace("'", "''")
        where = "n_coletivo = '{}'".format(texto)
        resultado = {
            "n_coletivo": numero_reurb_coletivo,
            "regra_layout": "atributo + INTERSECT",
        }
        try:
            resultado["atributo_quadras"] = _contar(
                quadra_origem, where, "diag_attr_q"
            )
            resultado["atributo_lotes"] = _contar(
                lote_origem, where, "diag_attr_l"
            )
            resultado["intersect_quadras"] = _contar_local(
                quadra_origem,
                where,
                bairro_layout,
                "INTERSECT",
                "diag_int_q",
            )
            resultado["intersect_lotes"] = _contar_local(
                lote_origem,
                where,
                bairro_layout,
                "INTERSECT",
                "diag_int_l",
            )
            resultado["centroide_quadras"] = _contar_local(
                quadra_origem,
                where,
                bairro_layout,
                "HAVE_THEIR_CENTER_IN",
                "diag_cen_q",
            )
            resultado["centroide_lotes"] = _contar_local(
                lote_origem,
                where,
                bairro_layout,
                "HAVE_THEIR_CENTER_IN",
                "diag_cen_l",
            )
            resultado["layout_quadras"] = _contar(
                quadra_layout, None, "diag_lay_q"
            )
            resultado["layout_lotes"] = _contar(
                lote_layout, None, "diag_lay_l"
            )
            resultado["codigos_quadra_layout"] = _codigos_quadra(quadra_layout)
        except Exception as erro:
            resultado["erro"] = str(erro)

        self.diagnostico.update(resultado)
        _log(messages, "Diagnóstico de contagem (núcleo/loteamento):")
        _log(
            messages,
            "  atributo n_coletivo: quadras={} lotes={}".format(
                resultado.get("atributo_quadras", "?"),
                resultado.get("atributo_lotes", "?"),
            ),
        )
        _log(
            messages,
            "  atributo + INTERSECT: quadras={} lotes={}".format(
                resultado.get("intersect_quadras", "?"),
                resultado.get("intersect_lotes", "?"),
            ),
        )
        _log(
            messages,
            "  atributo + centroide: quadras={} lotes={}".format(
                resultado.get("centroide_quadras", "?"),
                resultado.get("centroide_lotes", "?"),
            ),
        )
        _log(
            messages,
            "  layout usado: quadras={} lotes={}".format(
                resultado.get("layout_quadras", "?"),
                resultado.get("layout_lotes", "?"),
            ),
        )
        codigos = resultado.get("codigos_quadra_layout") or []
        if codigos:
            _log(
                messages,
                "  códigos no layout: {}".format(", ".join(codigos)),
            )
        if resultado.get("erro"):
            _log(messages, "  aviso do diagnóstico: {}".format(resultado["erro"]))
        return resultado

    def finalizar(self, ok=True, erro=None) -> None:
        """Devolve o scratch do Pro e grava diario.json na pasta da corrida."""
        self._restaurar_scratch()
        if not self.pasta_saida:
            return
        diario = {
            "id_execucao": self.id_execucao,
            "ok": bool(ok),
            "erro": None if erro is None else str(erro),
            "ferramenta": self.ferramenta,
            "numero_reurb": self.numero_reurb,
            "versao": self.versao,
            "pro": self.pro,
            "pasta_modulos": self.pasta_modulos,
            "pasta_saida": self.pasta_saida,
            "scratch_workspace": self.scratch_dir,
            "scratch_gdb": self.scratch_gdb,
            "inicio": self.inicio,
            "fim": datetime.now().isoformat(timespec="seconds"),
            "modulos_caixa": self.modulos,
            "diagnostico": self.diagnostico,
        }
        caminho = os.path.join(self.pasta_saida, "diario.json")
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(diario, arquivo, ensure_ascii=False, indent=2)

    def _restaurar_scratch(self) -> None:
        if self._restaurado:
            return
        self._restaurado = True
        try:
            import arcpy

            if self._ws_anterior is not None:
                arcpy.env.scratchWorkspace = self._ws_anterior
        except Exception:
            return


def iniciar_execucao(
    pasta_modulos,
    pasta_saida_usuario,
    ferramenta,
    numero_reurb,
    messages=None,
) -> ContextoExecucao:
    """Prepara scratch exclusiva, subpasta de saída e log da versão."""
    import arcpy

    if not pasta_saida_usuario:
        raise ValueError("Pasta de saída não informada.")

    ctx = ContextoExecucao()
    ctx.id_execucao = "{}_{}".format(
        time.strftime("%Y%m%d_%H%M%S"),
        os.getpid(),
    )
    ctx.ferramenta = ferramenta
    ctx.numero_reurb = numero_reurb or ""
    ctx.pasta_modulos = pasta_modulos
    ctx.inicio = datetime.now().isoformat(timespec="seconds")
    ctx.pro = _info_pro()

    raiz = achar_raiz_pacote(os.path.join(pasta_modulos, "x"))
    ctx.versao = ler_versao(raiz)
    ctx.modulos, ignorados = _modulos_caixa(raiz)

    ctx.pasta_saida = montar_pasta_execucao(
        pasta_saida_usuario,
        ferramenta,
        numero_reurb,
        ctx.id_execucao,
    )
    if os.path.exists(ctx.pasta_saida):
        raise ValueError(
            "A pasta desta execução já existe e a ferramenta não "
            "sobrescreve: {}".format(ctx.pasta_saida)
        )
    os.makedirs(ctx.pasta_saida)

    ctx.scratch_dir = os.path.join(
        tempfile.gettempdir(),
        "reurb_scratch_{}".format(ctx.id_execucao),
    )
    os.makedirs(ctx.scratch_dir, exist_ok=True)
    ctx._ws_anterior = arcpy.env.scratchWorkspace
    arcpy.env.scratchWorkspace = ctx.scratch_dir
    ctx.scratch_gdb = arcpy.env.scratchGDB

    _log(messages, "=== execução Desktop isolada ===")
    _log(messages, "versão do pacote: {}".format(ctx.versao.get("versao")))
    _log(messages, "VERSAO.txt: {}".format(ctx.versao.get("caminho")))
    _log(messages, "módulos desta ferramenta: {}".format(pasta_modulos))
    _log(
        messages,
        "ArcGIS Pro: {} {} (build {})".format(
            ctx.pro.get("produto") or "?",
            ctx.pro.get("versao") or "?",
            ctx.pro.get("build") or "?",
        ),
    )
    _log(messages, "Python: {}".format(ctx.pro.get("python")))
    _log(messages, "scratch exclusiva: {}".format(ctx.scratch_gdb))
    _log(messages, "pasta desta execução: {}".format(ctx.pasta_saida))
    if ignorados:
        _log(
            messages,
            "sessão do Pro ainda tinha {} módulo(s) de outra pasta; "
            "esta corrida usa só {}".format(ignorados, raiz),
        )
    for item in ctx.modulos:
        _log(
            messages,
            "módulo em cache: {} -> {}".format(
                item.get("nome"), item.get("arquivo")
            ),
        )
    return ctx
