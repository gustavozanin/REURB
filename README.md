# REURB

Ferramentas GIS para apoio aos processos de **Regularização Fundiária Urbana (REURB)** no ArcGIS Pro.

Este repositório concentra scripts Python, toolboxes (`.pyt`) e documentação das automações usadas para gerar plantas, memoriais, pranchas e demais entregas cartográficas.

## Estrutura

```text
REURB/
  ferramentas/          Toolboxes e scripts por produto
  REURB_ITERMA/         Pacote Desktop das plantas REURB (ArcGIS Pro, sem SDE)
  SHP/                  Shapefiles de apoio
  reurb.gdb/            Geodatabase local
  memoriais/            Memoriais gerados
```

Pastas de saída (`resultados/`, `tmp/`, `dados_exportados_arcgis/`) não entram no Git — são geradas pelas ferramentas.

## Ferramentas

| Pasta | Descrição | Documentação |
|-------|-----------|--------------|
| `REURB_ITERMA/REURB_Plantas_v0.14.0` | Caixa Desktop (núcleo, loteamento, vértices, institucional, memoriais de quadras) | [LEIA-ME](REURB_ITERMA/REURB_Plantas_v0.14.0/LEIA-ME_ANALISTA.txt) |
| `gerarplantanucleo` | Planta de núcleo, quadro de coordenadas e memorial descritivo | [README](ferramentas/gerarplantanucleo/README_AUTOMACAO_REURB.md) |
| `gerarpranchaloteamento` | PRANCHA 02 — Planta do loteamento | [README](ferramentas/gerarpranchaloteamento/README_PRANCHA_LOTEAMENTO.md) |
| `gerarplantageralbairro` | Planta geral do bairro e memoriais de quadras/eixos | [README](ferramentas/gerarplantageralbairro/README_PLANTA_GERAL_BAIRRO.md) |
| `gerarpranchaandamentoreurb` | Prancha de andamento REURB | [README](ferramentas/gerarpranchaandamentoreurb/README_PRANCHA_ANDAMENTO_REURB.md) |
| `gerarplantanucleo` (sync) | Sincronização de entregas com Google Drive | [README](ferramentas/gerarplantanucleo/README_SINCRONIZAR_ENTREGAS.md) |

## Requisitos

- ArcGIS Pro com licença ArcPy
- Python do ambiente ArcGIS Pro
- Acesso às camadas e geodatabases do projeto REURB no ambiente institucional

## Uso rápido

1. Adicione a toolbox desejada no ArcGIS Pro (arquivo `.pyt` dentro de cada pasta em `ferramentas/`).
2. Informe o `inputJson` conforme o README da ferramenta.
3. Os resultados saem em `resultados/<identificador>/` dentro da pasta da ferramenta.

Consulte o README específico de cada ferramenta para exemplos de JSON, camadas necessárias e arquivos gerados.

## Histórico de alterações

Resumo das mudanças locais nas ferramentas GIS: [RELATO_ALTERACOES_FERRAMENTAS_GIS.md](ferramentas/RELATO_ALTERACOES_FERRAMENTAS_GIS.md).
