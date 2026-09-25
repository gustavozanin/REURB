# -*- coding: utf-8 -*-
"""Testes puros da régua de confrontante da aresta (Erro 2 e Erro 5)."""

from types import SimpleNamespace
import unittest

from confrontantes import (
    _aceita_overlap,
    _eh_logradouro,
    _escolher_melhor_eixo,
    _herdar_eixo_vizinho_mais_longo,
    _texto_lote_vizinho,
    absorver_confrontantes_curtos,
    propagar_eixo_entre_vizinhos,
    resolver_confrontante_aresta,
)


class TestResolverConfrontanteAresta(unittest.TestCase):
    def test_testada_eixo_ganha_lote_no_canto(self):
        # Erro 5: P-02→P-03 com Lote 35 só no canto, rua à frente.
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua Bom Jesus',
            texto_lote='Lote 35',
            overlap_lote_m=1.2,
            comprimento_m=12.0,
        )
        self.assertEqual(texto, 'Rua Bom Jesus')

    def test_aresta_compartilhada_fica_com_lote(self):
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua Bom Jesus',
            texto_lote='Lote 54',
            overlap_lote_m=11.0,
            comprimento_m=12.0,
        )
        self.assertEqual(texto, 'Lote 54')

    def test_sem_eixo_usa_lote(self):
        texto = resolver_confrontante_aresta(
            texto_lote='Lote 08',
            overlap_lote_m=8.0,
            comprimento_m=8.0,
        )
        self.assertEqual(texto, 'Lote 08')

    def test_so_eixo(self):
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua Bom Jesus',
            comprimento_m=10.0,
        )
        self.assertEqual(texto, 'Rua Bom Jesus')

    def test_externo_linha_ganha_eixo_na_frente(self):
        # Layer 1 é linha (matrícula); overlap aceito (5 m) ganha da rua.
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua da Escola',
            texto_externo='Matrícula 111',
            overlap_externo_m=5.5,
            comprimento_m=12.0,
        )
        self.assertEqual(texto, 'Matrícula 111')

    def test_lote_na_frente_ganha_externo(self):
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua Bom Jesus',
            texto_lote='Lote 54',
            overlap_lote_m=11.0,
            texto_externo='Matrícula 111',
            overlap_externo_m=8.0,
            comprimento_m=12.0,
        )
        self.assertEqual(texto, 'Lote 54')

    def test_lote_no_canto_nao_rouba_externo(self):
        texto = resolver_confrontante_aresta(
            texto_eixo='Rua da Escola',
            texto_lote='Lote 02',
            overlap_lote_m=1.2,
            texto_externo='Matrícula 111',
            overlap_externo_m=8.0,
            comprimento_m=12.0,
        )
        self.assertEqual(texto, 'Matrícula 111')


class TestAbsorverLogradouro(unittest.TestCase):
    def test_nao_absorve_rua_entre_lotes(self):
        segmentos = [
            {'de': 'P-01', 'confrontante': 'Lote 35', 'distancia': 20},
            {'de': 'P-02', 'confrontante': 'Rua Bom Jesus', 'distancia': 8},
            {'de': 'P-03', 'confrontante': 'Lote 35', 'distancia': 20},
        ]
        saida, log = absorver_confrontantes_curtos(segmentos, limite_m=15)
        self.assertEqual(saida[1]['confrontante'], 'Rua Bom Jesus')
        self.assertEqual(log, [])

    def test_absorve_lote_curto_entre_mesma_rua(self):
        segmentos = [
            {'de': 'P-01', 'confrontante': 'Rua Bom Jesus', 'distancia': 20},
            {'de': 'P-02', 'confrontante': 'Lote 35', 'distancia': 8},
            {'de': 'P-03', 'confrontante': 'Rua Bom Jesus', 'distancia': 20},
        ]
        saida, log = absorver_confrontantes_curtos(segmentos, limite_m=15)
        self.assertEqual(saida[1]['confrontante'], 'Rua Bom Jesus')
        self.assertEqual(len(log), 1)


class TestOverlapELogradouro(unittest.TestCase):
    def test_canto_curto_nao_e_frente(self):
        self.assertFalse(_aceita_overlap(1.0, 20.0))

    def test_frente_real_aceita(self):
        self.assertTrue(_aceita_overlap(12.0, 20.0))

    def test_eh_logradouro(self):
        self.assertTrue(_eh_logradouro('Rua Bom Jesus'))
        self.assertTrue(_eh_logradouro('MA-212'))
        self.assertFalse(_eh_logradouro('Lote 35'))
        self.assertFalse(_eh_logradouro('LOTE 32 A'))


class TestTextoLoteVizinho(unittest.TestCase):
    def test_lote_numerico_em_caixa_alta(self):
        self.assertEqual(_texto_lote_vizinho(34), 'LOTE 34')

    def test_lote_com_letra_em_caixa_alta(self):
        self.assertEqual(_texto_lote_vizinho('32 a'), 'LOTE 32 A')


class TestEscolherMelhorEixo(unittest.TestCase):
    def test_fica_o_eixo_mais_paralelo(self):
        aprovados = [
            (0.99, 40.0, 'Rua Longe'),
            (0.85, 12.0, 'MA-335'),
        ]
        self.assertEqual(_escolher_melhor_eixo(aprovados), 'Rua Longe')

    def test_empate_de_paralelismo_usa_menor_distancia(self):
        aprovados = [
            (0.80, 10.0, 'Rua A'),
            (0.80, 6.0, 'Rua B'),
        ]
        self.assertEqual(_escolher_melhor_eixo(aprovados), 'Rua B')

    def test_empate_de_distancia_usa_maior_paralelismo(self):
        aprovados = [
            (0.80, 10.0, 'Rua A'),
            (0.95, 10.0, 'Rua B'),
        ]
        self.assertEqual(_escolher_melhor_eixo(aprovados), 'Rua B')

    def test_lista_vazia(self):
        self.assertIsNone(_escolher_melhor_eixo([]))


class TestPropagarEHerdarEixo(unittest.TestCase):
    def test_propaga_so_entre_pendentes(self):
        por = {1: 'Rua A', 3: 'Rua A'}
        saida = propagar_eixo_entre_vizinhos(
            por, [1, 2, 3, 4], oids_pendentes=[2]
        )
        self.assertEqual(saida[2], 'Rua A')
        self.assertNotIn(4, saida)

    def test_nao_propaga_se_vizinhos_nao_concordam(self):
        por = {1: 'Rua A'}
        saida = propagar_eixo_entre_vizinhos(
            por, [1, 2, 3], oids_pendentes=[2]
        )
        self.assertNotIn(2, saida)

    def test_herda_do_vizinho_mais_longo(self):
        melhor = {1: 'Rua A', 3: 'Rua B'}
        segs = {
            1: {'shape': SimpleNamespace(length=20)},
            2: {'shape': SimpleNamespace(length=3)},
            3: {'shape': SimpleNamespace(length=8)},
        }
        n = _herdar_eixo_vizinho_mais_longo(melhor, [1, 2, 3], segs, {2})
        self.assertEqual(n, 1)
        self.assertEqual(melhor[2], 'Rua A')


if __name__ == '__main__':
    unittest.main()
