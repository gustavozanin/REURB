# Relato de alteracoes nas ferramentas REURB para repasse ao desenvolvedor GIS

Data do relato: 29/06/2026

Este documento resume as alteracoes feitas localmente nas ferramentas REURB durante a ausencia do desenvolvedor GIS responsavel. A ideia e contextualizar o que foi criado, o que foi alterado, quais problemas apareceram no ArcGIS/ArcPy e o que precisa ser revisado/implementado no ambiente ArcGIS oficial.

## Contexto geral

As ferramentas foram copiadas do ambiente ArcGIS para a pasta local:

```text
C:\REURB\ferramentas
```

Durante o periodo, foram feitos ajustes emergenciais para gerar entregas, corrigir comportamentos de layout/exportacao e criar novos produtos solicitados pela operacao REURB. O trabalho local ficou dividido entre:

- ferramentas antigas copiadas do ArcGIS;
- ferramentas antigas modificadas localmente;
- novas ferramentas criadas a partir de fluxos existentes;
- arquivos de apoio, JSONs de teste, resultados e exportacoes intermediarias.

Nao havia Git disponivel neste ambiente local no momento da revisao, entao o rastreamento abaixo foi feito por historico de conversas, datas de modificacao e leitura da estrutura dos arquivos.

## Ferramentas novas criadas

### 1. Prancha Andamento REURB

Diretorio:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb
```

Toolbox:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\GerarPranchaAndamentoREURB.pyt
```

Script principal:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\gerar_prancha_andamento_reurb.py
```

Finalidade:

Gerar o novo produto "Prancha Andamento REURB", associado a etapa de pre-vetorizacao. A ferramenta foi criada como uma camada de adaptacao sobre o motor da ferramenta de prancha de loteamento, reaproveitando a logica que ja exporta camadas atuais do APRX e monta a prancha.

Entradas iniciais criadas:

```text
C:\REURB\ferramentas\gerarpranchaandamentoreurb\inputs\prancha_andamento_reurb_primeiros.json
C:\REURB\ferramentas\gerarpranchaandamentoreurb\inputs\vila_socorro_051301592_2026.json
C:\REURB\ferramentas\gerarpranchaandamentoreurb\inputs\centro_051301595_2026.json
C:\REURB\ferramentas\gerarpranchaandamentoreurb\inputs\setor_maciel_051301596_2026.json
```

Coletivos usados nos primeiros testes:

```text
051301592/2026 - Vila Socorro
051301595/2026 - Centro
051301596/2026 - Setor Maciel
```

Observacao importante:

A sintaxe e a leitura dos JSONs foram validadas localmente, mas a geracao final depende do Python do ArcGIS Pro por causa do `arcpy` e do uso do APRX.

### 2. Memoriais de Quadras por Bairro

Diretorio:

```text
C:\REURB\ferramentas\gerarplantageralbairro
```

Toolbox:

```text
C:\REURB\ferramentas\gerarplantageralbairro\GerarMemoriaisQuadrasBairro.pyt
```

Script principal:

```text
C:\REURB\ferramentas\gerarplantageralbairro\gerar_memoriais_quadras_bairro.py
```

Finalidade:

Gerar memoriais descritivos das quadras, com um PDF individual por quadra e um PDF consolidado por bairro. O memorial inclui area, perimetro, vertices, azimutes, distancias e confrontacoes.

Resultados ja gerados localmente:

```text
C:\REURB\ferramentas\gerarplantageralbairro\resultados\memoriais_quadras\peri_mirim\centro\050601273_2026
C:\REURB\ferramentas\gerarplantageralbairro\resultados\memoriais_quadras\peri_mirim\campo_de_pouso\051201571_2026
```

Contagens conferidas:

```text
Centro: 30 memoriais individuais + consolidado
Campo de Pouso: 15 memoriais individuais + consolidado
```

Ponto tecnico relevante:

A ferramenta foi pensada para buscar camadas atualizadas dentro do ArcGIS Pro usando `aprxCamadas: "CURRENT"`. Fora da sessao do ArcGIS Pro, houve instabilidade ao tentar acessar camadas FeatureServer do APRX; por isso tambem foi mantido um modo alternativo por `shpQuadras`, apontando para shapefiles ja exportados.

### 3. Memoriais Lineares dos Eixos Viarios

Script:

```text
C:\REURB\ferramentas\gerarplantageralbairro\gerar_memoriais_eixos_bairro.py
```

Finalidade:

Gerar memoriais lineares dos eixos viarios. Como a camada `eixo_viario` esta em geometria de linha, ela nao fecha poligono e nao permite calculo de area. O produto correto para essa camada e um memorial linear com vertices sequenciais, azimutes, distancias, coordenadas e extensao total.

Resultados ja gerados localmente:

```text
C:\REURB\ferramentas\gerarplantageralbairro\resultados\memoriais_eixos\peri_mirim\centro\050601273_2026
C:\REURB\ferramentas\gerarplantageralbairro\resultados\memoriais_eixos\peri_mirim\campo_de_pouso\051201571_2026
```

Contagens conferidas:

```text
Centro: 18 eixos
Campo de Pouso: 13 eixos
```

Observacao:

Esse gerador ainda nao foi consolidado como uma toolbox `.pyt` propria, mas ja existe como script funcional.

### 4. Planta Geral por Bairro

Toolbox:

```text
C:\REURB\ferramentas\gerarplantageralbairro\GerarPlantaGeralBairro.pyt
```

Finalidade:

Gerar a planta geral do loteamento por bairro, tambem chamada nos resultados como Prancha 03 / Planta Geral de Quadras.

Produtos trabalhados:

```text
Centro - 050601273/2026
Campo de Pouso - 051201571/2026
```

Alteracoes de layout incorporadas:

- titulo no carimbo ajustado para "PLANTA GERAL DO LOTEAMENTO";
- camada "Frente de lote" removida da visualizacao;
- "Frente de lote" removida da legenda;
- manutencao das camadas principais: limite do bairro, quadras, lotes/numeracao, vertices e eixos conforme necessidade.

## Ferramentas existentes alteradas

### 1. Gerar Prancha Loteamento

Diretorio:

```text
C:\REURB\ferramentas\gerarpranchaloteamento
```

Toolbox:

```text
C:\REURB\ferramentas\gerarpranchaloteamento\GerarPranchaLoteamento.pyt
```

Script mais alterado:

```text
C:\REURB\ferramentas\gerarpranchaloteamento\gerar_prancha_loteamento_arcgis.py
```

Principais mudancas:

- exportacao das camadas atuais do ArcGIS Pro/APRX por `n_coletivo`;
- suporte ao uso de `exportarCamadasArcGIS: true`;
- filtro principal por `n_coletivo`;
- fallback espacial para casos em que a selecao por atributo vem incompleta;
- ajuste para nao aceitar quadra vizinha quando a intersecao espacial traz uma feicao a mais indevida;
- definicao de World Imagery / Imagery da Esri na planta de situacao;
- remocao da camada "Frente de lote" da planta e da legenda;
- titulo da planta ajustado para "PLANTA GERAL DO LOTEAMENTO";
- lista de beneficiarios gerada por Python externo quando o Python do ArcGIS nao possui `reportlab`;
- conferencia de calculo de area e perimetro em SIRGAS 2000 / UTM 23S (`EPSG:31983`);
- geracao e copia de PDFs finais para pastas de entrega.

Casos conferidos:

```text
Centro - 050601273/2026
Campo de Pouso - 051201571/2026
```

Contagens observadas nos testes:

```text
Centro:
- 453 lotes
- 30 quadras corretas apos ajuste
- PDF final com 5 paginas

Campo de Pouso:
- 356 lotes
- 15 quadras
- PDF final com lista anexada
```

Problema encontrado:

Para o Centro, a selecao por `n_coletivo` retornava 30 quadras corretas, mas a intersecao espacial retornava 31, trazendo uma quadra vizinha de outro `n_coletivo`. A regra foi ajustada para que a selecao espacial so substitua a selecao por atributo quando o ganho for grande o suficiente para indicar que a selecao original veio claramente incompleta. No caso de diferenca pequena, como 30 para 31, a ferramenta mantem o filtro por `n_coletivo`.

### 2. Gerar Planta Nucleo

Diretorio:

```text
C:\REURB\ferramentas\gerarplantanucleo
```

Toolbox:

```text
C:\REURB\ferramentas\gerarplantanucleo\GerarPlantaNucleo.pyt
```

Arquivos relevantes alterados/criados no periodo:

```text
C:\REURB\ferramentas\gerarplantanucleo\gerar_planta.py
C:\REURB\ferramentas\gerarplantanucleo\gerar_memorial_descritivo.py
C:\REURB\ferramentas\gerarplantanucleo\exportar_camadas_iterma.py
C:\REURB\ferramentas\gerarplantanucleo\gerar_quadro_areas.py
C:\REURB\ferramentas\gerarplantanucleo\gerar_quadro_areas_trabalhadas.py
C:\REURB\ferramentas\gerarplantanucleo\gerar_png_quadro_vertices_completo.py
C:\REURB\ferramentas\gerarplantanucleo\sincronizar_entregas_drive.py
```

Resumo:

Houve expansao do fluxo da planta de nucleo com geracao de quadros, memoriais, exportacao de camadas e automacao de entregas. Essa pasta precisa ser revisada com cuidado antes de publicar no ArcGIS, pois recebeu alteracoes em varios auxiliares.

### 3. Gerar Planta REURB

Diretorio:

```text
C:\REURB\ferramentas\gerarplantareurb
```

Toolbox:

```text
C:\REURB\ferramentas\gerarplantareurb\GerarPlantaREURB.pyt
```

Situacao:

Parece ser uma das ferramentas antigas/base copiadas do ArcGIS. Houve uma conversa sobre erro no ArcGIS Server:

```text
ERROR 000358: Invalid expression logradouro IN ()
```

Causa provavel:

O codigo monta uma clausula SQL do tipo:

```text
logradouro IN ()
```

quando a lista de eixos/logradouros esta vazia. Isso gera expressao invalida no ArcPy.

Ponto de atencao:

O thread onde esse erro foi discutido foi interrompido, entao nao ha confirmacao de correcao concluida nessa pasta. Recomenda-se revisar especialmente:

```text
C:\REURB\ferramentas\gerarplantareurb\exporta_camadas_para_layout.py
```

e qualquer ponto equivalente em `gerarplantanucleo`, procurando por construcoes como:

```text
IN {tuple(...)}
```

sem tratamento para lista vazia.

### 4. Gestao Equipe

Diretorio:

```text
C:\REURB\ferramentas\gestaoequipe
```

Toolbox:

```text
C:\REURB\ferramentas\gestaoequipe\GestaoEquipe.pyt
```

Situacao:

Nao apareceu como foco das alteracoes recentes. Parece ferramenta antiga/base, sem mudancas relevantes no periodo deste relato.

## Dificuldades encontradas no ArcGIS / ArcPy

### 1. Instabilidade com camadas do APRX fora da sessao do ArcGIS Pro

Em alguns testes standalone, camadas vindas do APRX apareceram como referencias temporarias do tipo `GPLYR...`, e o ArcPy falhou ao usar `MakeFeatureLayer`, `ListFields` ou exportacoes subsequentes.

Sintomas observados:

```text
ERROR 000229
GPLYR...
Referencia de camada invalida fora da sessao interativa
```

Impacto:

Nem sempre foi possivel abrir o APRX e exportar as camadas atualizadas em processo standalone. Para contornar, algumas ferramentas aceitam:

- `aprxCamadas: "CURRENT"` quando rodadas dentro do ArcGIS Pro;
- caminho direto para shapefiles ja exportados quando a geracao precisa rodar fora do Pro.

Recomendacao:

No ambiente oficial, preferir rodar as ferramentas dentro do ArcGIS Pro/ArcGIS Server de forma que as camadas estejam disponiveis como datasets validos. Se for publicar como GP Service, testar bem o comportamento com FeatureServer e com camada do projeto.

### 2. FeatureServer nao aceito diretamente como dataset em alguns fluxos

Tentou-se usar `dataSource`/URL limpa do FeatureServer para consultar/exportar camadas. Em alguns pontos, o ArcPy nao aceitou a URL diretamente como dataset para `ListFields` ou `MakeFeatureLayer`.

Recomendacao:

Se a ferramenta oficial for consumir FeatureServer, avaliar uma destas abordagens:

- usar `arcpy.conversion.FeatureClassToFeatureClass` a partir de layer valida no projeto;
- criar camada temporaria dentro da sessao ativa do ArcGIS Pro;
- consumir o REST API diretamente quando o ambiente tiver rede/DNS liberado;
- padronizar exportacao previa das camadas para GDB/SHP temporario antes de montar os produtos.

### 3. Python do ArcGIS sem `reportlab`

Na geracao de lista de beneficiarios e PDFs auxiliares, o Python interno do ArcGIS nao tinha `reportlab`.

Mensagem observada:

```text
No module named 'reportlab'
```

Contorno aplicado:

A ferramenta passou a tentar gerar pelo Python do ArcGIS e, se falhar, chamar um Python externo com `reportlab` disponivel.

Recomendacao:

No ambiente oficial, decidir uma estrategia:

- instalar `reportlab` no ambiente Python do ArcGIS;
- manter fallback para Python externo controlado;
- substituir a geracao PDF por biblioteca ja homologada no ambiente.

### 4. Selecao espacial trazendo feicoes indevidas

No caso do Centro, a selecao espacial por intersecao trouxe uma quadra vizinha de outro `n_coletivo`. A selecao por atributo estava correta.

Regra ajustada:

Manter `n_coletivo` como filtro principal. Usar intersecao espacial apenas quando a diferenca indicar claramente que o atributo veio incompleto, nao quando a intersecao traz so uma feicao a mais.

Recomendacao:

Validar esse criterio com o desenvolvedor GIS antes de publicar, porque ele e uma decisao de negocio/geoprocessamento:

- lotes podem precisar de fallback espacial quando `n_coletivo` esta incompleto;
- quadras sao mais sensiveis a pegar vizinhas por intersecao;
- o ideal e registrar no log qual regra foi usada.

### 5. SQL `IN ()` invalido

Erro observado em ferramenta antiga:

```text
ERROR 000358: Invalid expression logradouro IN ()
```

Recomendacao:

Toda montagem de SQL com lista deve tratar lista vazia. Exemplo de regra esperada:

- se a lista estiver vazia, nao rodar o `Select`;
- ou usar uma expressao sempre falsa, como `1 = 0`;
- ou aplicar outra camada/regra de fallback.

## Produtos e resultados ja conferidos

### Prancha 02 - Planta do Loteamento

Campo de Pouso:

```text
Processo: 051201571/2026
Lotes: 356
Quadras: 15
Lista anexada
Area conferida: 337.815,5937 m2
Perimetro conferido: 2.657,4841 m
Sistema de calculo: SIRGAS 2000 / UTM 23S - EPSG:31983
```

Centro:

```text
Processo: 050601273/2026
Lotes: 453
Quadras corretas: 30
PDF final: 5 paginas
Quadra vizinha removida apos ajuste da selecao espacial
```

### Memoriais de Quadras

```text
Centro: 30 memoriais individuais + consolidado
Campo de Pouso: 15 memoriais individuais + consolidado
```

### Memoriais Lineares dos Eixos

```text
Centro: 18 eixos
Campo de Pouso: 13 eixos
```

### Prancha Andamento REURB

```text
Ferramenta criada
JSONs iniciais criados
Sintaxe validada
Geracao final ainda depende de validacao no ArcGIS Pro
```

## Arquivos/documentos auxiliares existentes

```text
C:\REURB\ferramentas\gerarpranchaloteamento\README_PRANCHA_LOTEAMENTO.md
C:\REURB\ferramentas\gerarpranchaloteamento\MAPEAMENTO_CAMADAS_REURB_ITERMA.md
C:\REURB\ferramentas\gerarplantageralbairro\README_PLANTA_GERAL_BAIRRO.md
C:\REURB\ferramentas\gerarpranchaandamentoreurb\README_PRANCHA_ANDAMENTO_REURB.md
C:\REURB\ferramentas\gerarplantanucleo\README_AUTOMACAO_REURB.md
C:\REURB\ferramentas\gerarplantanucleo\README_SINCRONIZAR_ENTREGAS.md
```

## Checklist sugerido para o desenvolvedor GIS

1. Comparar o ambiente oficial ArcGIS com a pasta local `C:\REURB\ferramentas`.
2. Priorizar revisao de `gerarpranchaloteamento`, pois foi a ferramenta mais alterada e ja esta sendo usada para entregas.
3. Validar a regra de selecao por `n_coletivo` versus intersecao espacial, especialmente para quadras.
4. Testar `GerarPranchaLoteamento.pyt` dentro do ArcGIS Pro com:
   - Centro `050601273/2026`;
   - Campo de Pouso `051201571/2026`.
5. Publicar/instalar a nova ferramenta `GerarPranchaAndamentoREURB.pyt` apenas apos testar a geracao final no ArcGIS Pro.
6. Avaliar se `GerarMemoriaisQuadrasBairro.pyt` deve entrar no ambiente oficial como ferramenta propria.
7. Transformar `gerar_memoriais_eixos_bairro.py` em toolbox `.pyt`, se o memorial linear dos eixos virar produto recorrente.
8. Corrigir definitivamente qualquer ocorrencia de SQL com `IN ()`.
9. Definir estrategia oficial para dependencia `reportlab`.
10. Decidir se os dados temporarios devem sair em SHP, GDB temporario ou pasta de resultados controlada.
11. Limpar ou separar resultados gerados, `tmp`, `temp`, `__pycache__` e arquivos de teste antes de empacotar/publicar.

## Observacao final

As alteracoes foram feitas para manter a producao andando durante a ausencia do responsavel GIS. Algumas decisoes foram pragmaticas para resolver entregas urgentes, especialmente os contornos para instabilidade do ArcPy com camadas do APRX e a ausencia de `reportlab` no Python do ArcGIS. Antes de levar tudo para producao, recomenda-se uma revisao tecnica completa e testes dentro do mesmo ambiente em que as ferramentas serao executadas.
