# Rastreabilidade entre os scripts anteriores e este repositório

Este repositório consolida scripts anteriormente executados nas Etapas 1–5.
A lógica original de cálculo da Etapa 4 e do detector online foi preservada.
As alterações principais foram de organização de pastas e portabilidade:

- `analises/modelo_exploratorio_etapa1.py`: substituídos os caminhos fixos de `/mnt/data/...` pelos argumentos `--csv` e `--out`.
- `analises/etapa2_modelos_regime.py`: substituídos os caminhos fixos pelos argumentos `--windows` e `--out`.
- `analises/etapa3_indicadores_fisicos.py` e `analises/etapa4_ciclos.py`: reaproveitados com sua interface original de linha de comando.
- `analises/sensibilidade_regras.py`: reaproveitado próximo a `etapa4_ciclos.py`, de que depende.
- `testes/verificar_equivalencia.py`: o caminho padrão da referência mudou para `resultados_referencia/alertas_referencia_etapa4.csv`.
- `iot_monitor/`: código reutilizado para HTTP local, persistência SQLite e detecção incremental.
- `notebooks/`: novos roteiros com explicações e chamadas aos scripts; mostram execução e verificações em Python.

Os artefatos `resultados_referencia/` registram os resultados originais; resultados de novas execuções vão para `resultados/` (fora do controle de versão). O CSV bruto não acompanha o repositório.

**Rigor científico**: parâmetros e horizontes foram escolhidos exploratoriamente com conhecimento retrospectivo dos dados. A reprodução computacional não transforma o estudo em validação prospectiva independente.
