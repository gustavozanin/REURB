# -*- coding: utf-8 -*-
"""Confrontante no trecho De→Para, igual à linha da tabela."""

import unittest

from memorial_narrativo import gerar_texto_memorial


class TestMemorialDePara(unittest.TestCase):
    def test_confrontante_fica_no_vertice_de(self):
        segmentos = [
            {
                'de': 'P-001',
                'para': 'P-002',
                'confrontante': 'Rua Venâncio',
                'azimute': "45°00'00\"",
                'distancia': 10,
                'E': 1,
                'N': 1,
                'este_para': 2,
                'norte_para': 2,
            },
            {
                'de': 'P-002',
                'para': 'P-001',
                'confrontante': 'Rua Piauí',
                'azimute': "135°00'00\"",
                'distancia': 10,
                'E': 2,
                'N': 2,
                'este_para': 1,
                'norte_para': 1,
            },
        ]
        texto = gerar_texto_memorial(segmentos)
        self.assertIn(
            'Do vértice P-001, confrontando com Rua Venâncio',
            texto,
        )
        self.assertIn(
            'Do vértice P-002, confrontando com Rua Piauí',
            texto,
        )
        self.assertNotIn(
            'até o vértice P-002, confrontando com Rua Piauí',
            texto,
        )


if __name__ == '__main__':
    unittest.main()
