# -*- coding: utf-8 -*-
"""Caixa única das ferramentas Desktop de plantas REURB.

No Catalog aparece como "REURB Plantas (Desktop)". Cada ferramenta
continua na pasta original; daqui só se aponta para elas.
"""
import hashlib
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader


def _raiz_pacote():
    aqui = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(os.path.join(aqui, "gerarplantanucleo")):
        return aqui
    candidatos = []
    for nome in os.listdir(aqui):
        candidato = os.path.join(aqui, nome)
        if (
            os.path.isdir(candidato)
            and nome.lower().startswith("reurb_plantas")
            and os.path.isdir(os.path.join(candidato, "gerarplantanucleo"))
        ):
            candidatos.append(candidato)
    if candidatos:
        candidatos.sort(key=lambda p: os.path.basename(p).lower(), reverse=True)
        return candidatos[0]
    raise RuntimeError(
        "Não achei o pacote REURB_Plantas (pasta gerarplantanucleo). "
        "Deixe este .pyt na raiz do pacote ou em C:\\REURB\\REURB_ITERMA, "
        "ao lado da pasta REURB_Plantas_v*."
    )


def _chave_modulo(caminho):
    """Evita misturar versões: a chave é o caminho absoluto do .pyt."""
    absoluto = os.path.normcase(os.path.normpath(os.path.abspath(caminho)))
    digest = hashlib.md5(absoluto.encode("utf-8")).hexdigest()[:16]
    return "reurb_caixa_" + digest


def _carregar_classe(relativo_pyt, nome_classe):
    caminho = os.path.normpath(os.path.join(_raiz_pacote(), relativo_pyt))
    if not os.path.isfile(caminho):
        raise RuntimeError(f"Toolbox não encontrada: {caminho}")
    nome_mod = _chave_modulo(caminho)
    if nome_mod in sys.modules:
        return getattr(sys.modules[nome_mod], nome_classe)
    loader = SourceFileLoader(nome_mod, caminho)
    spec = importlib.util.spec_from_loader(nome_mod, loader)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome_mod] = modulo
    loader.exec_module(modulo)
    return getattr(modulo, nome_classe)


class _FerramentaPacote(object):
    """Espelha a ferramenta original sem copiar a lógica."""

    _relativo_pyt = ""
    _nome_classe = ""

    def __init__(self):
        original = _carregar_classe(self._relativo_pyt, self._nome_classe)()
        self._original = original
        self.label = original.label
        self.description = getattr(original, "description", "")
        self.canRunInBackground = getattr(
            original, "canRunInBackground", False
        )

    def getParameterInfo(self):
        return self._original.getParameterInfo()

    def isLicensed(self):
        fn = getattr(self._original, "isLicensed", None)
        return fn() if fn else True

    def updateParameters(self, parameters):
        fn = getattr(self._original, "updateParameters", None)
        if fn:
            return fn(parameters)

    def updateMessages(self, parameters):
        fn = getattr(self._original, "updateMessages", None)
        if fn:
            return fn(parameters)

    def execute(self, parameters, messages):
        return self._original.execute(parameters, messages)

    def postExecute(self, parameters):
        fn = getattr(self._original, "postExecute", None)
        if fn:
            return fn(parameters)


class GerarPlantaNucleoDesktopTool(_FerramentaPacote):
    _relativo_pyt = os.path.join(
        "gerarplantanucleo", "gerarplantanucleo", "GerarPlantaNucleo.pyt"
    )
    _nome_classe = "GerarPlantaNucleoDesktopTool"


class GerarPlantaLoteamentoDesktopTool(_FerramentaPacote):
    _relativo_pyt = os.path.join(
        "gerarplantaloteamento",
        "gerarplantaloteamento",
        "GerarPlantaLoteamento.pyt",
    )
    _nome_classe = "GerarPlantaLoteamentoDesktopTool"


class GerarPlantaVerticesConfrontantesMemorialDesktopTool(_FerramentaPacote):
    _relativo_pyt = os.path.join(
        "gerarplantaverticesconfrontantesmemorial",
        "gerarplantaverticesconfrontantesmemorial",
        "GerarPlantaVerticesConfrontantesMemorial.pyt",
    )
    _nome_classe = "GerarPlantaVerticesConfrontantesMemorialDesktopTool"


class GerarMemoriaisQuadrasDesktopTool(_FerramentaPacote):
    _relativo_pyt = os.path.join(
        "gerarmemoriaisquadras",
        "gerarmemoriaisquadras",
        "GerarMemoriaisQuadras.pyt",
    )
    _nome_classe = "GerarMemoriaisQuadrasDesktopTool"


class GerarPlantaInstitucionalDesktopTool(_FerramentaPacote):
    _relativo_pyt = os.path.join(
        "gerarplantainstitucional",
        "gerarplantainstitucional",
        "GerarPlantaInstitucional.pyt",
    )
    _nome_classe = "GerarPlantaInstitucionalDesktopTool"


class Toolbox(object):
    def __init__(self):
        self.label = "REURB Plantas (Desktop)"
        self.alias = "REURBPlantas"
        self.tools = [
            GerarPlantaNucleoDesktopTool,
            GerarPlantaLoteamentoDesktopTool,
            GerarPlantaVerticesConfrontantesMemorialDesktopTool,
            GerarMemoriaisQuadrasDesktopTool,
            GerarPlantaInstitucionalDesktopTool,
        ]
