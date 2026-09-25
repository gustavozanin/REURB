# -*- coding: utf-8 -*-
"""Testes do isolador Desktop (sem ArcGIS)."""

import os
import tempfile
import unittest

from execucao_desktop import (
    achar_raiz_pacote,
    chave_modulo,
    copiar_sem_sobrescrever,
    ler_versao,
    montar_pasta_execucao,
    slug_processo,
)


class TestExecucaoDesktop(unittest.TestCase):
    def test_chave_modulo_diferente_por_caminho(self):
        a = chave_modulo(r"C:\REURB\v1\execucao_desktop.py")
        b = chave_modulo(r"C:\REURB\v2\execucao_desktop.py")
        self.assertTrue(a.startswith("reurb_ed_"))
        self.assertNotEqual(a, b)

    def test_chave_modulo_estavel(self):
        caminho = r"C:\REURB\REURB_ITERMA\REURB_Plantas_v0.13.2\x.pyt"
        self.assertEqual(chave_modulo(caminho, "reurb_caixa_"), chave_modulo(caminho, "reurb_caixa_"))

    def test_slug_processo(self):
        self.assertEqual(slug_processo("062502287/2026"), "062502287_2026")
        self.assertEqual(slug_processo(""), "sem_processo")

    def test_montar_pasta_execucao(self):
        pasta = montar_pasta_execucao(
            r"C:\saida",
            "nucleo",
            "062502287/2026",
            "20260922_221000_1234",
        )
        self.assertEqual(
            pasta,
            os.path.join(
                r"C:\saida",
                "nucleo_062502287_2026_20260922_221000_1234",
            ),
        )

    def test_ler_versao_e_raiz(self):
        raiz = os.path.dirname(os.path.abspath(__file__))
        self.assertEqual(achar_raiz_pacote(__file__), raiz)
        dados = ler_versao(raiz)
        self.assertEqual(dados.get("versao"), "0.14.0")
        self.assertTrue(os.path.isfile(dados.get("caminho")))

    def test_modulos_caixa_so_desta_pasta(self):
        import sys
        import types
        from execucao_desktop import _modulos_caixa

        raiz = os.path.dirname(os.path.abspath(__file__))
        fake_ok = types.ModuleType("reurb_caixa_teste_ok")
        fake_ok.__file__ = os.path.join(raiz, "REURB_Plantas.pyt")
        fake_old = types.ModuleType("reurb_caixa_teste_old")
        fake_old.__file__ = r"C:\REURB\REURB_ITERMA\REURB_Plantas_v0.13.2\x.pyt"
        sys.modules[fake_ok.__name__] = fake_ok
        sys.modules[fake_old.__name__] = fake_old
        try:
            itens, ignorados = _modulos_caixa(raiz)
            arquivos = [i["arquivo"] for i in itens]
            self.assertTrue(any(raiz in a for a in arquivos))
            self.assertTrue(ignorados >= 1)
            self.assertFalse(any("v0.13.2" in a for a in arquivos))
        finally:
            sys.modules.pop(fake_ok.__name__, None)
            sys.modules.pop(fake_old.__name__, None)

    def test_copiar_sem_sobrescrever(self):
        with tempfile.TemporaryDirectory() as tmp:
            origem = os.path.join(tmp, "origem.txt")
            destino = os.path.join(tmp, "sub", "copia.txt")
            with open(origem, "w", encoding="utf-8") as arquivo:
                arquivo.write("ok")
            copiar_sem_sobrescrever(origem, destino)
            with self.assertRaises(ValueError):
                copiar_sem_sobrescrever(origem, destino)


if __name__ == "__main__":
    unittest.main()
