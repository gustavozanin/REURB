# -*- coding: utf-8 -*-
"""Vértices de controle do projeto, sem densificar arco."""

import unittest

from memorial_quadras_core import pontos_controle_de_geojson


class TestPontosControle(unittest.TestCase):
    def test_anel_reto(self):
        dados = {
            'rings': [[
                [0, 0], [10, 0], [10, 10], [0, 10], [0, 0],
            ]]
        }
        aneis = pontos_controle_de_geojson(dados)
        self.assertEqual(len(aneis), 1)
        self.assertEqual(len(aneis[0]), 5)

    def test_arco_so_pontos_de_edicao(self):
        # Início, arco até (10, 10) com centro, depois fecha.
        dados = {
            'curveRings': [[
                [0, 0],
                {'a': [[10, 10], [5, 0], 0]},
                [0, 10],
                [0, 0],
            ]]
        }
        aneis = pontos_controle_de_geojson(dados)
        self.assertEqual(aneis[0], [
            (0.0, 0.0),
            (10.0, 10.0),
            (0.0, 10.0),
            (0.0, 0.0),
        ])

    def test_curveRings_ganha_de_rings(self):
        dados = {
            'curveRings': [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            'rings': [[[0, 0], [1, 0], [1, 1], [0.5, 0.5], [0, 1], [0, 0]]],
        }
        aneis = pontos_controle_de_geojson(dados)
        self.assertEqual(len(aneis[0]), 4)


if __name__ == '__main__':
    unittest.main()
