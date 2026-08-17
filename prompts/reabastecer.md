<!--
Item de REABASTECIMENTO — o que faz a fila durar mais que o bloco destilado.

Artefato do produto (ADR-014). Não é código: é uma linha `- [ ]` que entra na
**cauda** do `.loop/QUEUE.md` e se reproduz a cada volta. Funciona porque o hook
lê o `QUEUE.md` do disco no instante do `Stop`, depois de o agente já ter escrito
nele — então um turno que acrescenta itens muda a fila que o próprio hook vai
contar.

Existe porque `fila zerada` é a condição **#4** da cadeia e o relógio é a **#6**:
armar por tempo (`--duracao 6h`) esperando que o loop puxe o próximo documento
não funciona — a fila vazia dispara sempre antes. Medido em três rodadas do EOP,
onde o `--duracao` nunca chegou a valer.

Como usar: troque o que está entre ‹› pelo que vale no seu repositório e cole a
linha no fim do `QUEUE.md`. Uma linha só; a indentação das continuações é o que
mantém o item legível sem quebrar o `- [ ]`.

⚠️ O escopo declarado não é enfeite. Sem ele o reabastecimento puxa trabalho que
deveria ter parado para perguntar — e o loop decide sozinho no lugar do dono.
-->

- [ ] REABASTECER: escolher o próximo bloco de trabalho ainda não coberto, usando
      ‹índice do que existe› e ‹índice do que já foi entregue› como mapa, e
      **respeitando o escopo declarado abaixo**. Ler a documentação dele
      **inteira** — não amostrar —, e destilar o próximo bloco em linhas `- [ ]`
      no fim deste arquivo, uma por unidade **executável sozinha** (quem lê o
      item é um turno futuro que não tem este contexto). Registrar, em uma linha,
      **o que a triagem mediu** — inclusive hipótese que morreu, para a próxima
      volta não repetir a varredura. **Terminar acrescentando um novo item
      REABASTECER idêntico a este** — *exceto* se a medição disser que não há
      bloco em escopo: aí **não reponha**, escreva o veredito com os números, e
      deixe a fila zerar. Fila zerada com veredito é o desfecho certo; bloco
      fabricado para cumprir a cláusula é o pior de todos.
      **Escopo:** ‹o que pode entrar›. **Para e pergunta:** ‹o que nunca entra
      sem decisão do dono — dinheiro, autenticação, dado de produção, o que for›.

---

## Por que cada cláusula está aí

Todas saíram de uma rodada de 10 voltas no EOP (17/08/2026), não de desenho.

| Cláusula | O que ela impede |
|---|---|
| `ainda não coberto`, com dois índices | Reabastecer com trabalho já entregue. O índice velho foi o primeiro defeito que a própria rodada achou. |
| **escopo declarado** + "para e pergunta" | O loop decidir sozinho onde a decisão é do dono. É o que separa reabastecimento de agente solto. |
| ler **inteira**, não amostrar | Proxy de palavra-chave errou 3 das 7 triagens da rodada. Medir pelo que a casa escreve, não pelo que se espera que ela escreva. |
| uma unidade **executável sozinha** | O item é lido por um turno futuro sem o contexto de agora. Item que depende do chat morre na primeira parada. |
| registrar **o que mediu** | Hipótese que mede zero é resultado, não desperdício — e sem registro a volta seguinte repete a varredura. |
| **repor o item**, com escape | Sem repor, a fila zera na parada seguinte e o loop encerra com relógio sobrando. Repondo sem insumo, o agente **fabrica** trabalho — e prosa sem lastro num repo onde a documentação é fonte de verdade é pior que parar. |

A rodada que fechou o padrão: 14 paradas seguidas sem encerrar, 13 delas com o
REABASTECER como item, fila de 22 → 66 itens, e no fim o próprio agente quebrou a
cláusula de reposição com as sete hipóteses tabeladas — três viraram bloco, três
mediram zero. **O padrão terminou por veredito, não por esquecimento.**
