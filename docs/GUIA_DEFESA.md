# Guia de demonstração ao professor — RailPulse (8 a 12 minutos)

**Antes:** rode notebook 01 e notebook 05. Quando tiver CSV original no Drive, rode 02 e 04 e salve seus outputs. Não dependa de upload de 209 MB minutos antes da apresentação.

## O que dizer e executar

1. **Problema (1 min):** falhas da unidade de ar (APU) podem interromper operações; sensores permitem monitoramento de pressão e carga. Dados reais MetroPT-3, não medições próprias.
2. **Origem e auditoria (1 min):** abrir UCI, explicar frequência efetiva ~10 s, hash SHA-256, 1.516.948 registros, falhas reportadas.
3. **Método (2 min):** mostrar `analises/etapa4_ciclos.py`: estado sob carga quando corrente >2 A e `DV_eletric` >0,5; pressão inicial 7,7–8,5 bar; intervalo entre amostras >30 s interrompe fase; limiar de recuperação P99 (188 s) e meta 9,7 bar.
4. **Notebook 01 (2 min):** executar recorte F3; mostrar gráfico da TP3 e o alerta `09:51:38`; explicar que a regra só acessa dados passados.
5. **Comparação e sensibilidade (2 min):** mostrar 33 vs. 136 alertas e P95/P97,5/P99; menos alertas não significa necessariamente melhor diagnóstico.
6. **Notebook 05 e painel (2 min):** mostrar recepção HTTP, base SQLite, 303 registros / 3 alertas; no PC, abrir painel local `127.0.0.1:8765`.
7. **Limitações (1 min):** 3 falhas avaliadas, rótulos incompletos, critérios pós-hoc, IoT simulada, não previsão industrial validada.

## Respostas curtas a perguntas técnicas

**Qual linguagem?** Python 3 para dados, detecção, HTTP e SQLite; JavaScript/HTML/CSS para painel; LaTeX para artigo.

**Onde foi desenvolvido e pode ser executado?** Scripts Python locais; notebooks Jupyter que rodam no Colab; GitHub guarda fontes e documentação após publicação. O Colab não é um host público do servidor HTTP local.

**O GitHub executa o Python?** Não por publicar arquivos. O GitHub armazena versão e código. Para executar, use Colab, computador local, Actions configuradas ou outro ambiente de computação.

**O que é dado real e o que é simulação?** Os valores são leituras históricas reais do MetroPT-3; o envio HTTP é replay simulado de IoT, não sensores físicos próprios.

**O que são 190/190?** Equivalência entre detector retrospectivo e incremental (33 + 21 + 136); não acurácia de previsão.

**Por que não chamar os 20 alertas restantes de falsos positivos?** A fonte não possui rótulos exaustivos de todos os estados saudáveis.

**Por que 9,7 bar e 188 s?** 9,7 bar foi meta exploratória; 188 s é percentil 99 dos tempos de recuperação nos ciclos elegíveis de maio que atingiram a meta. Escolha pós-hoc deve ser explicitada.

**Quem escreveu o código?** Seja preciso quanto ao uso de assistência de IA e às suas próprias escolhas, testes, modificações e interpretações. O domínio do código é demonstrado executando e explicando, não ocultando o processo.

## Exercícios para seu domínio prático

- Altere o gráfico para mostrar temperatura ao lado da corrente e descreva o efeito observado.
- Troque o recorte para F2 e F4, anote os timestamps.
- Execute o detector no recorte NORMAL, verifique a ausência de alertas nesse exemplo (não garante ausência de defeito).
- Teste artificialmente uma lacuna de mais de 30 segundos em cópia de recorte e explique por que a fase é reiniciada.
- Ajuste *somente em um experimento extra identificado como simulação* o alvo de pressão e veja como o alerta muda; não apresente esse resultado como parte do artigo original.
- Explique por que a calibração deve usar dados anteriores e por que escolher variáveis pós-hoc causa viés, mesmo sem acesso a amostras futuras pelo algoritmo.
