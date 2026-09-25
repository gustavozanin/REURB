# Checklist rápido — erros comuns

Use esta página quando a ferramenta Desktop falhar.

| Mensagem / sintoma | Causa provável | O que fazer |
|--------------------|----------------|-------------|
| Número de REURB coletivo inexistente | `n_coletivo` não existe no Bairro | Confira o número (barra e ano). Busque no mapa. |
| Bairro em andamento | `status` diferente de 2 ou 4 | Aguarde conclusão da vetorização ou peça atualização do status. |
| Responsável técnico não preenchido | Campo vazio no Bairro (comum no FeatureServer) | Informe **Nome do RT** na ferramenta Desktop (deve existir no GDB auxiliar) ou peça preenchimento na edição. |
| Responsável técnico não cadastrado | Nome não está na tabela local | Atualizar GDB auxiliar **ou** informar Formação + CREA/CAU nos parâmetros opcionais. |
| ERROR 000824 / ferramenta sem licença | Licença Advanced indisponível na sessão | Rodar pela interface do ArcGIS Pro (Geoprocessing), não só pelo python.exe do terminal. |
| municipios não encontrada / GDB auxiliar | Pacote incompleto | Peça ao TI rodar `atualizar_gdb_auxiliar.py`. |
| Token / não consegue ler o serviço | Sem login no portal | Faça login no portal ITERMA no ArcGIS Pro e rode de novo. |
| Layout não encontrado | Projeto/layout de geração ausente | Confirme pastas `layout/` e `project_layout.aprx` da ferramenta. |
| Ferramenta muito lenta | Rede / FeatureServer | Aguarde; se repetir, avise o TI (filtro por processo já é aplicado). |
| Lote não é institucional (status=…) | Status do lote não é Municipal/Estadual | Use a ferramenta só para institucionais; confira Status de andamento. |
| Lote não existe na quadra | Chave REURB+quadra+lote sem feição | Confira quadra/lote no mapa (camada Lotes). |
| Ambiguidade: N feições com a mesma chave | Cadastro duplicado | Corrija o cadastro antes de gerar. |
| Situação/Observação do lote: … (aviso) | Cadastro com observação (ex. faixa de domínio) | Revise antes de protocolar; o PDF não inclui esse texto. |
| PDF/ZIP não aparecem | Pasta de saída inválida ou execução incompleta | Confira a **subpasta** da corrida (nome com data/pid) e o `diario.json`. |
| Já existe um arquivo neste caminho e a ferramenta não sobrescreve | Arquivo com o mesmo nome na pasta da corrida | Use outra pasta de saída ou apague só se for teste. |
| Log sem "execução Desktop isolada" | Toolbox antiga ainda no Python do Pro | Feche o ArcGIS Pro, abra de novo e dê Refresh na caixa 0.14.0. |
| No module named 'reportlab' | Sem permissão em Program Files, o pip instala em `%APPDATA%\\Python\\...`, pasta que o ArcGIS Pro ignora | **Memoriais de Quadras:** confirme que a pasta `gerarmemoriaisquadras\\gerarmemoriaisquadras\\libs` veio no pacote — ela já traz reportlab e pypdf, nada a instalar. **Demais ferramentas:** instale com `propy.bat -m pip install reportlab` (a toolbox tenta enxergar o site-packages do usuário). Se ainda falhar, peça ao TI instalar no ambiente `arcgispro-py3`, com permissão de escrita em Program Files. |
| Confrontante "LOTE DE TERCEIROS - NÃO IDENTIFICADO" | Segmento sem bairro vizinho, confrontante externo nem eixo viário | Esperado quando não houve levantamento; aparece na planta, CSV, memorial e quadro. |
| Confrontante saiu como bairro vizinho (ex. Portinho) em vez da matrícula | Confrontante Externo e bairro se tocam no mesmo trecho | Nesta versão a matrícula (layer Confrontante Externo) ganha do bairro vizinho. Regenere a planta. |
| Confrontante de lote institucional como `L00 - Q00` | Rótulo antigo | Deve sair `Lote 00` (padrão da Instituição). Regenere a planta. |
| Ruas da institucional trocadas (ex. MA-212 na testada oposta) | Lado externo da aresta invertido | Esta versão usa o polígono real do lote para nomear o eixo. Regenere. |
| Memorial de quadra sem Confrontante Externo | Layer 1 fora do recorte, sem campo `nome`, ou polígono afastado da aresta | A ferramenta recorta 50 m ao redor do bairro e casa com buffer de 5 m. Confira a camada no mapa e a mensagem do Geoprocessing. |
| Memorial sem brasão/logo | Arquivos em `layout/assets/` ausentes no pacote | Confira `brasao_maranhao.png` e `logo_governo_maranhao.png` na pasta da ferramenta. |

## Pré-requisitos antes de rodar

- [ ] Login no portal ITERMA
- [ ] Número do REURB correto
- [ ] Status 2 ou 4 no Bairro
- [ ] Responsável técnico preenchido
- [ ] Pasta de saída com permissão de escrita
- [ ] GDB auxiliar presente (preparado pelo TI)
