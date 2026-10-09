# MetroPT-3 - Etapa 4: ciclos e alertas de recuperação pneumática

**Situação:** pesquisa exploratória retrospectiva. **Não há validação prospectiva da previsão de falhas.** Nenhum sensor, controlador, ESP32 ou plataforma de IoT foi fisicamente implantado. A arquitetura IoT é uma possível etapa futura, utilizando simulação de transmissão dos registros históricos.

## Arquivos

- `etapa4_ciclos.py`: analisa o CSV original, separa episódios em carga, calcula tempo até a pressão-alvo e compara três regras de alerta com limiares calculados no período de calibração.
- `gerar_relatorio_etapa4.py`: cria cinco gráficos e o relatório técnico PDF.
- `verificar_etapa4.py`: testes de integridade, separação temporal e consistência com prefixos temporais truncados antes das falhas.
- `ciclos_carga.csv`: uma linha por fase sob carga (15.769), incluindo duração final *retrospectiva*. Não usar essa duração para disparar um alerta antes da fase terminar!
- `alertas_ciclos.csv`: alertas disparados online (sem dependência da duração futura). Campos `termino_carga` e `duracao_total_posteriormente_observada_s` são exclusivamente metadados retrospectivos.
- `avaliacao_falhas.csv`, `comparacao_regras.csv`, `perfis_antes_falhas.csv`: indicadores de avaliação.
- `parametros.json`, logs e cinco PNGs: configuração, auditoria, representações visuais.

## Fonte e versão

Os arquivos foram calculados sobre `MetroPT3(AirCompressor).csv` (1.516.948 registros, versão com intervalos majoritariamente próximos de 10 s). O arquivo original tem ~209 MB e **não é redistribuído no ZIP**. Verifique SHA-256 em `parametros.json` para garantir que usa a mesma versão.

Fonte oficial: [MetroPT-3, UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/791/metropt%2B3%2B), DOI `10.24432/C5VW3R`. A descrição entregue como `Data Description_Metro.pdf` contém a função dos sensores e os intervalos F1-F4. Trabalhamos com a versão efetivamente fornecida e não pressupomos que ela tenha 1 Hz como a aquisição original descrita na literatura.

## Reprodução

Instale Python com `numpy`, `pandas`, `matplotlib`, `reportlab`, `Pillow` (detalhes em `requirements.txt`). Coloque o CSV junto à pasta descompactada (um diretório acima), ou passe o caminho absoluto:

```bash
python etapa4_ciclos.py --csv '../MetroPT3(AirCompressor).csv' --out .
python verificar_etapa4.py --csv '../MetroPT3(AirCompressor).csv' --out .
python gerar_relatorio_etapa4.py --csv '../MetroPT3(AirCompressor).csv'
```

## Hipóteses e definição de alerta

- `em carga`: `Motor_current > 2 A` e `DV_eletric > 0,5`. São critérios de investigação operacional, não limites homologados.
- Nova fase: mudança do estado sob carga ou intervalo de telemetria `>30 s`. Conclusão observável requer transições sem lacuna em ambas as extremidades.
- Grupo de referência: fases com `TP3` inicial entre `7,7` e `8,5 bar`, duração `>=35 s` e conclusão observada. Referência escolhida exploratoriamente.
- Pressão-alvo: `TP3 >= 9,7 bar`. Meta analítica plausível, **não** especificação da APU. O valor não foi pré-registrado e a escolha está informada pelas inspeções prévias.
- Calibração: maio 1–22. Fases terminadas no intervalo e sem dados de F2–F4. Não há ajuste com futuros rótulos de teste.
- Teste: a partir de 23/05/2020. Horizontes de análise: 2 horas anteriores às falhas F2, F3, F4.
- Critério 1: tempo contínuo em carga superior ao P99 da **duração de fase** na calibração (`337,12 s`).
- Critério 2: tempo em carga superior ao P99 do **tempo até 9,7 bar** nos episódios que atingiram a meta na calibração (`188 s`), **sem ter alcançado 9,7 bar até o momento**.
- Critério 3: mesmo corte temporal (`188 s`) do critério 2, ignorando a pressão.
- Um alerta por fase. Descontinuidades de telemetria interrompem a contagem. Não inferimos operação através de lacunas.
- Os eventos conhecidos são descritivos: F1 18/04, F2 29/05–30/05, F3 05–07/06, F4 15/07. Eventos de teste F2–F4.

## Resultados principais

| Modelo | Alertas no teste | Fora das proximidades | Eventos com alertas em 2 h |
|---|---:|---:|---:|
| P99 de duração (carga longa) | 21 | 13 | 3 / 3 |
| P99 do tempo para 9,7 bar, com pressão | 33 | 20 | 3 / 3 |
| Apenas carga, limiar equivalente | 136 | 115 | 3 / 3 |

O critério com pressão teve primeiro alarme em F2 às 22:51:38 (ciclo que logo se recuperou), F3 às 09:51:38, F4 às 12:48:25. F2 também teve alerta associado à operação prolongada iniciada às 23:14:56, emitido às 23:18:04. Em F4, vários ciclos recuperam a pressão mesmo depois de alertados; o sinal aponta **lentidão de recuperação**, não diagnóstico confirmado de vazamento.

Para as janelas de 2 h anteriores, somente ciclos finalizados antes do evento foram utilizados nas estatísticas: F2 4 ciclos concluídos, mediana até 9,7 bar de 99 s; F3 5 e 99 s; F4 12 e 218 s. Na calibração, a mediana entre fases que atingiram a meta foi 99 s.

## O que NÃO podemos concluir

1. Não é correto dizer que os alarmes detectaram antecipadamente vazamentos reais: os relatórios não definem o instante físico de início e a ausência de anotações em outros períodos não certifica normalidade.
2. Contar um evento como "com pré-alerta" apenas significa coincidência dentro de 2 horas; alguns alertas correspondem a ciclos que se recuperaram normalmente.
3. **20 alertas fora das proximidades** não equivalem a 20 falsos positivos confirmados; são alarmes sem evento conhecido próximo, em uma verdade-terreno incompleta.
4. A pressão-alvo, o horizonte de 2 horas e as famílias de regras foram escolhidos em um processo iterativo que já inspecionara eventos de teste. Logo, resultados não são avaliação externa cega.
5. O percentil P99 de recuperação exclui ciclos censurados sem alcançar a meta, o que pode subestimar a cauda; os resultados exigem análise de sensibilidade e avaliação externa.
6. O fluxo é processamento histórico local. Não alegar implantação física de dispositivos IoT, rede MQTT ou infraestrutura em tempo real.

## Verificações

`verificar_etapa4.py` carrega o CSV original e reconstrói os alarmes sem registros futuros até três cortes anteriores a F2, F3 e F4; os timestamps dos alertas anteriores aos cortes são comparados com o processamento completo. O teste passou nos três pontos, conforme `testes_etapa4.log`.

## Referências da base

- Davari, N. et al. (2021). *MetroPT-3 Dataset*. UCI Machine Learning Repository. DOI: `10.24432/C5VW3R`.
- Veloso, B. et al. (2022). *The MetroPT dataset for predictive maintenance*. *Scientific Data*, 9, 764. DOI: `10.1038/s41597-022-01877-3`.

## Próxima etapa

Criar demonstração de **reprodução sequencial (replay)** de registros históricos via uma arquitetura IoT **simulada**: sensores representados pelos campos MetroPT-3 → publicador local → consumidor/armazenamento → regras de alerta em fluxo → painel e registro de alertas. Testar latência, perdas e tolerância a lacunas. Essa demonstração documenta a solução de IoT sem inventar uma implantação física.
