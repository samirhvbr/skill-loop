# Documentação técnica — skill-LOOP

Índice de `docs/`. Documentação **durável** mora aqui; notas de trabalho, escopo
e estado em [`.continue/`](../.continue/); contrato normativo em
[`SPEC.md`](../SPEC.md); prompt do produto em [`prompts/`](../prompts/).

> Projeto em **F1**: motor entregue e testado (72 testes), **sem operação em
> trabalho real**. O que estiver marcado com ⛔ no `SPEC.md` é lacuna conhecida,
> não esquecimento.

## Nesta pasta

| Arquivo | O que é |
|---|---|
| [decisoes.md](decisoes.md) | **ADRs.** ADR-001 a ADR-011 (decisões da conversa de 16/08) + pendências P-01 a P-06. Decisão nova entra aqui. |

## Fora desta pasta

| Arquivo | O que é |
|---|---|
| [../README_br.md](../README_br.md) | **O produto, canônico.** Problema medido, tese, classificador, pipeline, condições de fim, limitações declaradas. |
| [../README.md](../README.md) | Tradução para inglês — porta de entrada do repositório público. |
| [../SPEC.md](../SPEC.md) | **Normativo.** Gatilho, classificação, transcript, `reason`, condições de fim, formato do `.loop/`. |
| [../SECURITY.md](../SECURITY.md) | Modelo de ameaça (T-01 a T-07). **Leitura obrigatória.** |
| [../skill/loop/SKILL.md](../skill/loop/SKILL.md) | A skill: como destilar a fila, armar, e o que o agente deve fazer durante o loop. |
| [../prompts/continuacao.md](../prompts/continuacao.md) | O `reason` de continuação — artefato do produto. |
| [../version.md](../version.md) | Fonte de verdade da versão, gatilhos de bump, formato de commit, changelog. |
| [../CLAUDE.md](../CLAUDE.md) / [../AGENTS.md](../AGENTS.md) | Regras de quem desenvolve este repo. Espelhados — editar os dois. |
| [../.continue/escopo-projeto.md](../.continue/escopo-projeto.md) | Fases F0–F3 + v2, com critério de pronto. |
| [../.continue/estado-atual.md](../.continue/estado-atual.md) | Onde o projeto está e o que precisa do Samir. |
| [../.claude/README.md](../.claude/README.md) | Perfil de modelo e postura de permissões. |

## Por onde começar

- **Entender o produto** → `../README_br.md`, depois `decisoes.md`.
- **Vai mexer no classificador** → ADR-004 e ADR-005 primeiro, e rode a mutação
  antes de mudar qualquer léxico. Os fixtures em `../tests/fixtures/` são
  mensagens **reais anonimizadas**: são a calibração, não exemplo. Os originais
  estão em `../fixtures-reais/` (fora do git).
- **Vai mexer no prompt de continuação** → §4 do `../SPEC.md`, e bump obrigatório.
- **Vai mexer em guarda-corpo ou condição de fim** → T-02 e T-03 do
  `../SECURITY.md`, e ADR-010.

## Convenções

- PT-BR em tudo; `README.md` (inglês) acompanha o `README_br.md` no mesmo commit.
- Documento novo aqui entra **neste índice** no mesmo commit.
- Sem link para arquivo inexistente.
- Fato observado ≠ inferência ≠ recomendação.
- Controle só conta com teste que **falha quando o controle é desligado** —
  registre quantos testes a mutação derruba.
