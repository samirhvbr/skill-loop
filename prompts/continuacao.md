<!--
Template do `reason` que o hook Stop devolve para retomar o agente.
Artefato do produto — mudar aqui é mudar comportamento (bump em version.md).

Placeholders (str.format): iteracao, max_iteracoes, kind, sinal, entry, item,
pendentes, feitos, objetivo, bloco_ask, bloco_colhidos.

Regras de escrita deste prompt (aprendidas em campo, SPEC.md §4):
- Dizer que o chat NÃO está sendo lido. Sem isso o agente volta a resumir.
- Dar o item exato. "Continua" sozinho faz o agente re-planejar e derivar.
- Dar a condição de parada explícita, senão ele para na primeira dúvida.
- Nunca pedir confirmação de nada aqui — este texto existe para eliminá-la.
-->
[LOOP-WORK · iteração {iteracao}/{max_iteracoes} · sua última mensagem foi arquivada como {kind} em {entry}]

**Ninguém está lendo o chat agora.** O relato que você acabou de escrever já foi
gravado em disco e será lido depois, em lote. Escrever resumo de novo é trabalho
perdido: siga produzindo.

**Item atual da fila** (`.loop/QUEUE.md` — {feitos} feito(s), {pendentes} pendente(s)):

> {item}

{bloco_ask}{bloco_colhidos}
**Como seguir:**

1. Execute o item atual **até o fim** — não relate progresso parcial, não peça
   confirmação, não proponha alternativas para eu escolher.
2. Marque `- [x]` no `.loop/QUEUE.md` quando concluir.
3. Vá **direto** para o próximo item pendente, no mesmo turno, sem me avisar.
4. Se descobrir trabalho novo necessário, acrescente-o como `- [ ]` na fila em
   vez de me perguntar se deve fazer.
5. **Se o item atual depende de uma decisão que só eu posso tomar** — dinheiro,
   contrato, ADR, autenticação, ato irreversível, ou qualquer pergunta aberta
   endereçada a mim —, troque o `- [ ]` dele por `- 🔒` no `.loop/QUEUE.md`,
   registre a pergunta em uma linha, e **siga para o próximo item pendente no
   mesmo turno**. Não é encerramento e não é desistência: é tirar da fila de
   execução o que não é executável por você. `- [x]` ali seria mentira, e
   deixar `- [ ]` devolve o mesmo item à sua frente na próxima parada, para
   sempre.

**Só encerre o turno de verdade se** uma destas for verdade:

- a fila zerou (nenhum `- [ ]` restante — itens `- 🔒` não contam, eles já
  saíram da fila de execução);
- existe o arquivo `.loop/STOP`;
- a próxima ação é **destrutiva ou irreversível** e não está coberta por uma
  premissa já registrada (apagar dados, migração sem volta, push forçado,
  gastar dinheiro, mexer em produção, mandar mensagem para terceiro);
- você está **tecnicamente bloqueado** por algo fora do seu alcance (credencial
  ausente, serviço fora do ar) — e aí diga exatamente o que falta, em uma linha.

⚠️ **Depender de decisão minha não é motivo para encerrar** — é motivo para
marcar `- 🔒` e seguir (item 5). Encerrar ali gasta a parada sem tirar o item da
frente, e a parada seguinte recebe o mesmo item: foi assim que uma rodada no EOP
girou 25 vezes na mesma caixa em 18/09/2026.

Objetivo do loop: {objetivo}
