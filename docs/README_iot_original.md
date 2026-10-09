# Etapa 5 — RailPulse: simulação de monitoramento IoT com MetroPT-3

## 1. O que está implementado

Este projeto demonstra uma **arquitetura computacional de telemetria industrial em fluxo** usando dados históricos reais do compressor de um trem, disponibilizados no MetroPT-3. Não há protótipo físico. O transporte é **HTTP em localhost**, não MQTT; o banco de dados é **SQLite**. O painel funciona no navegador e não utiliza serviços externos.

```text
MetroPT-3 (CSV, 2020)
  │ publicador replay.py (amostra por amostra; velocidade ajustável)
  ▼
POST /api/reading  ──>  servidor HTTP Python  ──>  SQLite (leituras)
                              │
                              ▼
                       detector causal (3 regras)
                              │
                              ▼
                        SQLite (alertas)
                              │
                              ▼
                    painel web em localhost
```

O detector reproduz exatamente as regras, os parâmetros, os alertas e os instantes da **Etapa 4**, para o período de teste a partir de 23/05/2020. Os horários de falha documentados NÃO entram no detector.

## 2. Execução no Windows (passo a passo)

É necessário **Python 3.9 ou superior**. Não é necessário instalar bibliotecas adicionais para executar o protótipo.

1. Extraia o ZIP para uma pasta, por exemplo `C:\MetroPT3_Etapa5`.
2. Abra um terminal **dentro dessa pasta**.
3. Inicie o servidor (mantenha esse terminal aberto):

   ```powershell
   py -3 rodar_servidor.py
   ```

4. Abra **http://127.0.0.1:8765** no navegador.
5. Abra outro terminal na mesma pasta e reproduza F3:

   ```powershell
   py -3 rodar_replay.py --demo F3 --speed 150 --reset
   ```

6. Acompanhe os gráficos e os alertas no painel. O registro histórico próximo de **2020-06-05 09:51:38** acionará o alerta principal de recuperação lenta da pressão, sem que o sistema conheça previamente o início documentado da falha.

Para reprodução instantânea (sem pausas), use `--speed 0`. Para ritmo mais lento e agradável em apresentação, use `--speed 50`. Em uma nova execução, use `--reset` para iniciar nova sessão. O botão **Reiniciar sessão** no painel também apaga as leituras e alertas da sessão local.

Se o Windows não reconhecer `py -3`, substitua pelo comando `python`.

### Outros cenários

```powershell
py -3 rodar_replay.py --demo F2 --speed 150 --reset
py -3 rodar_replay.py --demo F4 --speed 150 --reset
py -3 rodar_replay.py --demo NORMAL --speed 150 --reset
```

O `--demo NORMAL` é um recorte histórico com 364 amostras sem alertas pelas três regras. Esse período **não é rotulado como operacionalmente isento de defeitos**: significa apenas ausência de alertas segundo os critérios implementados.

### CSV completo

O ZIP **não inclui** os 209 MB do CSV original. Para reproduzir outra janela do arquivo original:

```powershell
py -3 rodar_replay.py --csv "C:\dados\MetroPT3(AirCompressor).csv" --from "2020-06-05 09:30:00" --to "2020-06-05 10:20:00" --speed 150 --reset
```

Para transmitir o CSV completo, omita `--from` e `--to` e use `--speed 0`. O processamento com HTTP/SQLite de 1,5 milhão de mensagens poderá ser demorado; para verificar os 190 alertas de forma rápida, use o teste offline descrito abaixo.

## 3. Regras embarcadas

Uma fase sob carga começa quando `Motor_current > 2 A` E `DV_eletric > 0,5`. Um intervalo entre leituras superior a 30 s encerra a fase anterior. Somente ciclos que começam com `TP3` entre **7,7 e 8,5 bar** são elegíveis para alertas, conforme Etapa 4.

1. **Principal — pressão não recuperada:** o ciclo ultrapassa **188 s** sob carga e a pressão `TP3` ainda não atingiu **9,7 bar em nenhum instante desde o início da fase**.
2. **Comparador — carga prolongada:** tempo sob carga ultrapassa **337,12 s**, independentemente da pressão.
3. **Controle — apenas carga:** tempo sob carga ultrapassa **188 s**, independentemente da pressão.

O limiar de 9,7 bar é **exploratório**, não uma especificação de fabricante. Os percentis de tempo foram definidos com base nos dados de calibração de 01 a 22/05/2020, conforme Etapa 4. Os limiares foram definidos no processo retrospectivo do estudo; não são hiperparâmetros pré-registrados de um ensaio prospectivo.

Os sinais exibidos são `TP3`, `Motor_current`, `Oil_temperature` e `DV_eletric`. Corrente/temperatura auxiliam a interpretação; a regra principal de detecção utiliza o estado operacional, a pressão e o tempo sob carga.

## 4. Comprovação de equivalência (CSV inteiro)

Com o CSV original, execute:

```powershell
py -3 testes\verificar_equivalencia.py --csv "C:\dados\MetroPT3(AirCompressor).csv"
```

Esse teste **não envia HTTP**: aplica o mesmo detector em memória nas leituras cronológicas e compara, por método e timestamp, os resultados com `resultados/alertas_referencia_etapa4.csv`.

Resultados obtidos nesta entrega:

| Regra | Etapa 4 | Processamento em fluxo | Igualdade |
|---|---:|---:|---|
| Pressão não recuperada | 33 | 33 | Sim |
| Carga prolongada | 21 | 21 | Sim |
| Apenas carga | 136 | 136 | Sim |
| **Total** | **190** | **190** | **Sim** |

Foram processadas **1.516.948 amostras**, gerando **15.769 episódios sob carga**. Todos os 190 pares `(método, timestamp)` coincidiram. Veja `resultados/equivalencia.json`.

## 5. Testes automáticos

```powershell
py -3 -m unittest discover -s testes -p "test_*.py" -v
```

Os testes cobrem: comportamento causal do limiar, pressão já recuperada, reinício após lacuna temporal, rejeição de NaN, ingestão HTTP+persistência SQLite e alertas da demonstração F3. `testes/validar_painel.py` é um teste opcional de imagem, executado na infraestrutura de desenvolvimento e **requer Playwright**, mas não é necessário para o usuário executar o sistema.

A imagem `resultados/painel_demonstracao_F3.png` foi gerada com um snapshot real da API, renderizado em navegador sem acesso de rede, porque a infraestrutura de teste bloqueou navegação do Chromium por localhost. A integração HTTP do replay foi verificada separadamente.

## 6. Endpoints e armazenamento

| Endpoint | Método | Função |
|---|---|---|
| `/` | GET | Painel web |
| `/api/reading` | POST | Receber uma amostra JSON e retornar alertas imediatamente |
| `/api/status` | GET | Indicadores, configuração e última leitura |
| `/api/readings?limit=400` | GET | Leituras recentes |
| `/api/alerts?limit=100` | GET | Alertas recentes |
| `/api/export_alerts.csv` | GET | Exportar alertas para análise |
| `/api/reset` | POST | Reiniciar sessão e limpar banco |

O servidor escuta **somente 127.0.0.1 por padrão**. Não há autenticação, criptografia TLS, gestão de certificados, QoS MQTT, armazenamento em nuvem nem tolerância a falhas industriais. **Não publique este servidor na Internet** e não o utilize para acionar equipamentos ou em decisões críticas. Em reinício do servidor, o estado do detector é reconstruído pelas leituras já gravadas em SQLite.

## 7. Interpretação científica e limites

- **Demonstrado:** fluxo de dados de um transmissor histórico, API de recepção, persistência, detector causal amostra a amostra, alertas e painel visual; equivalência exata com a Etapa 4.
- **Não demonstrado:** aquisição de sensores físicos, comunicação MQTT real, transmissão industrial confiável, implantação em ambiente ferroviário, redução operacional de paradas ou validade prospectiva da previsão de falhas.
- Os registros de falha são incompletos e os horários registrados não representam necessariamente o começo físico de uma avaria.
- O registro histórico disponibilizado possui espaçamento predominante de aproximadamente 10 s; o protótipo reproduz timestamps originais sem interpolação ou ritmo fabricado. O fator `--speed` acelera apenas a reprodução dos intervalos temporais existentes.
- As três falhas de avaliação F2, F3 e F4 têm pré-alertas retrospectivos em 2 h pela regra principal, mas também existem 20 alertas fora das proximidades dos eventos conhecidos. Parte dos ciclos alertados recuperou a pressão depois, e isso não demonstra falha física.
- Os valores de calibração e o próprio desenho das regras foram desenvolvidos exploratoriamente com conhecimento retrospectivo do dataset; por isso, o experimento ainda não caracteriza uma validação prospectiva independente.
- A inferência industrial correta neste momento é **detecção experimental de ciclos de recuperação pneumática lenta**, e não um sistema comprovado de previsão de vazamentos.

## 8. Fonte de dados

Davari, N.; Veloso, B.; Ribeiro, R.; Gama, J. *MetroPT-3 Dataset*. UCI Machine Learning Repository, 2021. DOI: **10.24432/C5VW3R**.

Veloso, B. et al. *The MetroPT dataset for predictive maintenance*. *Scientific Data*, v. 9, artigo 764, 2022. DOI: **10.1038/s41597-022-01877-3**.

Arquivo original esperado na análise de equivalência: `MetroPT3(AirCompressor).csv`, SHA-256 conforme `parametros_etapa4.json`.

## 9. Próxima fase sugerida para o artigo

Etapa 6: desenho experimental definitivo, comparação quantitativa contra detectores de referência, definição explícita de métrica de eventos/alertas e análise de falsos alarmes; em seguida, redação do artigo e roteiro de apresentação de 10 minutos. 
