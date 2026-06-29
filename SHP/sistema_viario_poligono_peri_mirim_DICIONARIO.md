# Sistema Viario Poligono - Peri Mirim

Arquivo:

```text
C:\REURB\SHP\sistema_viario_poligono_peri_mirim.shp
```

Sistema de coordenadas:

```text
SIRGAS 2000 - EPSG:4674
```

## Finalidade

Camada poligonal para representar a area ocupada pelo sistema viario, diferente do eixo viario em linha.

Use esta camada para:

- representar a faixa real da rua na planta;
- calcular area e perimetro do sistema viario;
- gerar memorial descritivo de poligonos de rua;
- dissolver por bairro ou por logradouro quando necessario.

## Campos

| Campo | Tipo | Uso |
|---|---|---|
| `cod_via` | Texto 50 | Codigo unico da via. Use o mesmo codigo na camada de eixo em linha, quando existir. |
| `lograd` | Texto 120 | Nome do logradouro, rua, avenida, travessa ou rodovia. |
| `tipo_log` | Texto 30 | Tipo do logradouro: RUA, TRAVESSA, AVENIDA, MA, VIA LOCAL, etc. |
| `bairro` | Texto 80 | Nome do bairro/nucleo. |
| `n_coletiv` | Texto 50 | Numero do processo coletivo, exemplo `050601273/2026`. |
| `larg_m` | Double | Largura media ou adotada da via, em metros. |
| `area_m2` | Double | Area do poligono em metros quadrados. Calcular em UTM 23S. |
| `perim_m` | Double | Perimetro do poligono em metros. Calcular em UTM 23S. |
| `situacao` | Texto 30 | Situacao: EXISTENTE, PROJETADA, REGULARIZADA, AJUSTADA. |
| `origem` | Texto 50 | Fonte: LEVANTAMENTO, IMAGEM, DESENHO, BUFFER_EIXO, AJUSTE_TECNICO. |
| `obs` | Texto 254 | Observacoes tecnicas. |

## Regras De Desenho

1. Cada feicao deve ser um poligono fechado representando a area da via.
2. Evite sobreposicao em cruzamentos quando o objetivo for memorial por logradouro.
3. Para planta geral, pode ser gerada uma camada dissolvida com todo o sistema viario do bairro.
4. Calcule `area_m2` e `perim_m` em SIRGAS 2000 / UTM 23S, nao em coordenadas geograficas.
5. Mantenha `cod_via` igual entre o eixo em linha e o poligono, quando houver correspondencia.

## Sugestao De Valores

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
