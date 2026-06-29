# Mapeamento de Camadas - REURB ITERMA

Fonte principal para automacao local:

```text
C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx
```

FeatureServer base:

```text
https://www.arcgis.iterma.ma.gov.br/server/rest/services/CAMADAS_ITERMA/REURB_ITERMA/FeatureServer
```

## Camadas Identificadas

| Uso no fluxo | Nome no APRX | FeatureServer | Geometria | Campos principais | Observacao |
|---|---|---:|---|---|---|
| Eixo viario / confrontacoes | Eixo Viario | 0 | Polyline | `logradouro`, `campo`, `globalid` | Usado para confrontacoes/logradouros; no loteamento exporta por intersecao com o bairro. |
| Bairro / perimetro | Bairro | 8 | Polygon | `nome`, `n_coletivo`, `status`, `globalid` | Fonte preferencial do perimetro/area/perimetro por REURB coletivo e bairro. |
| Lotes / beneficiarios | Lotes | 9 | Polygon | `n_coletivo`, `quadra`, `lote`, `nome`, `cpf_cnpj`, `bairro`, `status`, `validado`, `rua` | Fonte da prancha de loteamento e lista de beneficiarios. |
| Quadras | Quadras | 10 | Polygon | `n_coletivo`, `quadra`, `bairro`, `globalid` | Apoio para planta geral/quadras. |
| Marcacao de frente | marcacao_frente_lote_ma_reurb | local SHP | Point | `quadra`, `lote`, `n_coletivo`, `municipio`, `bairro`, `obs` | Camada local: `C:\REURB\ferramentas\gerarplantageralbairro\marcacoes\marcacao_frente_lote_ma_reurb.shp`. |

## Automacao Implementada

A ferramenta `GerarPranchaLoteamentoTool` aceita agora o modo:

```json
"exportarCamadasArcGIS": true
```

Quando ligado, o fluxo abre o APRX local, encontra as camadas vivas e exporta para SHP antes da geracao da prancha.

Arquivos exportados:

```text
C:\REURB\ferramentas\gerarpranchaloteamento\dados_exportados_arcgis\<municipio>\<bairro>\<numero>\bairro.shp
C:\REURB\ferramentas\gerarpranchaloteamento\dados_exportados_arcgis\<municipio>\<bairro>\<numero>\lotes.shp
C:\REURB\ferramentas\gerarpranchaloteamento\dados_exportados_arcgis\<municipio>\<bairro>\<numero>\eixo_viario.shp
C:\REURB\ferramentas\gerarpranchaloteamento\dados_exportados_arcgis\<municipio>\<bairro>\<numero>\marcacao_frente_lote.shp
```

## Filtros Usados

- Bairro: tenta `n_coletivo + nome`, depois `n_coletivo`, depois `nome`.
- Lotes: tenta `n_coletivo`, depois `bairro`.
- Eixo viario: seleciona por intersecao espacial com o bairro exportado.
- Marcacao de frente: tenta `n_coletivo + bairro + municipio`, depois `n_coletivo`, depois `bairro + municipio`.

## Exemplo - Prancha Loteamento Centro com camadas atuais

```json
{"exportarCamadasArcGIS":true,"aprxCamadas":"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx","dados":{"numeroProcessoColetivo":"050601273/2026","municipio":"Peri Mirim","bairro":"Centro"},"responsavelTecnico":"leandro_miranda_da_silva","anexarLista":true}
```

## Exemplo - Prancha Loteamento Campo de Pouso com camadas atuais

```json
{"exportarCamadasArcGIS":true,"aprxCamadas":"C:\Users\gusta\OneDrive\Documentos\ArcGIS\Projects\REURB_ITERMA\REURB_ITERMA.aprx","dados":{"numeroProcessoColetivo":"051201571/2026","municipio":"Peri Mirim","bairro":"Campo de Pouso"},"responsavelTecnico":"bruna_silva_sa_pereira","anexarLista":true}
```
