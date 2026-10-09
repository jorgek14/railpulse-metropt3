# RailPulse — Monitoramento de compressores ferroviários com MetroPT-3

Repositório acadêmico **reproduzível** para uma investigação retrospectiva de monitoramento de pressão pneumática e telemetria IoT **simulada**. Linguagem: **Python 3** (análise com pandas/NumPy/scikit-learn, servidor HTTP, SQLite e painel HTML/CSS/JavaScript). Artigo em LaTeX/IEEEtran.

> **Limite científico:** os alertas anteciparam horários *documentados* de falhas, e não necessariamente o instante físico do vazamento. Não houve sensores embarcados, transmissão industrial ou validação prospectiva. A meta de 9,7 bar e a faixa inicial são exploratórias.

## Como começar (sem CSV de 209 MB)

- Veja `notebooks/01_demonstracao_rapida.ipynb`: recorte histórico F3, gráfico, execução de 3 regras e conferência do alerta de `2020-06-05 09:51:38`.
- Para demonstrar transporte HTTP real e persistência SQLite em Colab: `notebooks/05_http_sqlite_e_painel.ipynb`.
- Para visualizar o painel no **seu computador**, execute o servidor conforme seção a seguir.

### Executar no Google Colab

1. [Abra o Colab](https://colab.research.google.com/) e carregue o `.ipynb` desejado (Arquivo → Fazer upload de notebook) ou selecione o notebook publicado no GitHub.
2. Execute a primeira célula. Ela pedirá o **ZIP do repositório RailPulse** (ou você poderá editar a variável `git_repo` para clonar sua conta após publicar).
3. Nos notebooks 02, 03 e 04, envie o CSV do [UCI MetroPT-3](https://archive.ics.uci.edu/dataset/791/metropt%2B3%2B) para a raiz de `Meu Drive` ou para `dados/`, sem inseri-lo no GitHub.
4. Execute as células na ordem. Consulte as mensagens de confirmação e os CSVs em `resultados/`.

> O ambiente do Colab é temporário. Salve o notebook no seu Drive/GitHub para preservar alterações e resultados. Publicar os notebooks não publica o CSV bruto.

### Executar no seu computador (Windows / Linux / macOS)

```bash
python -m pip install -r requirements.txt
python rodar_servidor.py
```

Depois abra `http://127.0.0.1:8765` no navegador. **Em outro terminal**:

```bash
python rodar_replay.py --demo F3 --speed 150 --reset
# Outros: F2, F4 ou NORMAL; speed 0 elimina esperas entre leituras
```

O servidor só escuta em `127.0.0.1`: não publique a API local na Internet nem a use para controlar equipamentos reais.

### Reproduzir o artigo a partir do CSV completo

Coloque `MetroPT3(AirCompressor).csv` em `dados/` (é ignorado pelo Git). Rode:

```bash
python scripts/auditar_csv.py --csv "dados/MetroPT3(AirCompressor).csv"
python analises/etapa4_ciclos.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/etapa4
python analises/verificar_etapa4.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/etapa4
python testes/verificar_equivalencia.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/equivalencia.json
python analises/sensibilidade_regras.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/sensibilidade
python -m unittest discover -s testes -p "test_*.py" -v
```

Para executar os modelos anteriores (Etapas 1–3):

```bash
python analises/modelo_exploratorio_etapa1.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/etapa1
python analises/etapa2_modelos_regime.py --windows resultados/etapa1/janelas_10min_baseline_exploratorio.csv --out resultados/etapa2
python analises/etapa3_indicadores_fisicos.py --csv "dados/MetroPT3(AirCompressor).csv" --out resultados/etapa3
```

## Estrutura

- `notebooks/`: cinco cadernos didáticos com células explicadas.
- `analises/`: scripts das Etapas 1 a 4 e análise de sensibilidade pós-hoc.
- `iot_monitor/`, `rodar_servidor.py`, `rodar_replay.py`, `web/`: protótipo IoT simulado com HTTP local, SQLite e painel.
- `dados_demo/`: quatro recortes reais pequenos para teste sem download do CSV completo.
- `resultados_referencia/`: saídas originais usadas para conferir a reprodução.
- `artigo_latex/`: código IEEEtran, BibTeX e figuras; compila em projeto LaTeX que disponha de IEEEtran.
- `testes/`: testes automáticos do detector e da integração; `.github/workflows/testes.yml` executa seis testes de amostra ao publicar commits no GitHub.
- `docs/NOTAS_ADAPTACOES.md`: registra as modificações dos caminhos dos scripts ao transferir para GitHub/Colab.
- `docs/`: documentação do dataset e instruções históricas.

## Resultados de referência publicados no artigo

| Critério | Total | Alertas nas 2 h anteriores (F2–F4) | Fora das proximidades conhecidas |
|---|---:|---:|---:|
| Recuperação lenta de pressão, P99, 188 s | 33 | 13 | 20 |
| Carga prolongada P99, 337,12 s | 21 | 7 | 13 |
| Apenas carga com corte de 188 s | 136 | 18 | 115 |

A verificação em fluxo reproduziu **190/190 pares de método e horário**. Isso confirma consistência de software, não precisão de previsão em uma nova instalação industrial.

## Proveniência e licença dos dados

Dados: Davari et al., *MetroPT-3 Dataset*, [UCI ML Repository](https://archive.ics.uci.edu/dataset/791/metropt%2B3%2B), DOI [10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R), licença **CC BY 4.0**. Publicação sobre a família MetroPT: Veloso et al. (2022), DOI [10.1038/s41597-022-01877-3](https://doi.org/10.1038/s41597-022-01877-3). O CSV integral deve ser obtido do fornecedor dos dados.

Arquivo esperado, SHA-256:
`db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24`

O código está sob MIT (arquivo LICENSE). Os dados e os artigos de terceiros **não** são relicenciados pela licença do código. Recortes de dados incluídos conservam a atribuição ao MetroPT-3.

## Transparência, autoria e defesa

O material foi desenvolvido de forma iterativa **com assistência de IA na implementação, organização, documentação e revisão**. A autoria acadêmica deve corresponder às contribuições efetivas de cada pessoa e às regras da instituição. Execute você mesmo os notebooks, altere parâmetros, justifique decisões e registre os resultados obtidos. **Não apresente execução e implementação assistidas como realizadas sozinho se isso não refletir o processo.**

Veja `docs/GUIA_DEFESA.md` para perguntas, explicação dos algoritmos e roteiro de demonstração.
