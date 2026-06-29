# Sistema Viario Poligono - REURB MA

Arquivo:

```text
C:\REURB\SHP\sistema_viario_poligono_reurb_ma.shp
```

Sistema de coordenadas:

```text
SIRGAS 2000 - EPSG:4674
```

## Finalidade

Camada estadual para representar a area ocupada pelo sistema viario dos projetos REURB no Maranhao.

Use esta camada para:

- publicar um modelo unico no ArcGIS Online;
- mapear poligonos de ruas, travessas, avenidas e vias locais;
- calcular area e perimetro do sistema viario;
- gerar plantas e memoriais poligonais por municipio, bairro/nucleo, processo ou logradouro.

## Campos

| Campo | Tipo | Uso |
|---|---|---|
| `cod_via` | Texto 50 | Codigo unico da via. Recomenda-se combinar municipio, processo e numero sequencial. |
| `lograd` | Texto 120 | Nome do logradouro. |
| `tipo_log` | Texto 30 | Tipo: RUA, TRAVESSA, AVENIDA, RODOVIA, VIA LOCAL. |
| `municipio` | Texto 80 | Nome do municipio. |
| `uf` | Texto 2 | Unidade federativa. Para este projeto, `MA`. |
| `bairro` | Texto 80 | Bairro, quando existir. |
| `nucleo` | Texto 80 | Nucleo REURB ou localidade. Pode repetir o bairro quando for o mesmo conceito. |
| `n_coletiv` | Texto 50 | Numero do processo coletivo. |
| `larg_m` | Double | Largura media/adotada da via em metros. |
| `area_m2` | Double | Area em metros quadrados, calculada em UTM adequado. |
| `perim_m` | Double | Perimetro em metros, calculado em UTM adequado. |
| `situacao` | Texto 30 | EXISTENTE, PROJETADA, REGULARIZADA ou AJUSTADA. |
| `origem` | Texto 50 | LEVANTAMENTO, IMAGEM, DESENHO, BUFFER_EIXO ou AJUSTE_TECNICO. |
| `resp_tec` | Texto 120 | Responsavel tecnico ou equipe responsavel pela geometria. |
| `data_ref` | Data | Data de referencia da geometria ou levantamento. |
| `obs` | Texto 254 | Observacoes tecnicas. |

## Regras De Uso

1. Cada feicao deve ser um poligono fechado da area ocupada pela via.
2. Preencher sempre `municipio`, `uf`, `nucleo` ou `bairro`, e `n_coletiv` quando houver processo.
3. Manter `cod_via` estavel para relacionar com a camada de eixo em linha.
4. Calcular `area_m2` e `perim_m` em sistema projetado adequado. Para a maior parte do Maranhao ocidental/central use SIRGAS 2000 / UTM 23S; para areas a leste, avaliar UTM 24S quando tecnicamente necessario.
5. Para planta geral estadual/municipal, pode-se dissolver por `municipio`, `nucleo`, `bairro` ou `n_coletiv`.

## Valores Sugeridos

`uf`:

```text
MA
```

`tipo_log`:

```text
RUA
TRAVESSA
AVENIDA
RODOVIA
VIA LOCAL
```

`situacao`:

```text
EXISTENTE
PROJETADA
REGULARIZADA
AJUSTADA
```

`origem`:

```text
LEVANTAMENTO
IMAGEM
DESENHO
BUFFER_EIXO
AJUSTE_TECNICO
```
