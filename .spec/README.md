# Spec-Driven Development

Este repositório utiliza o **Spec-Driven Development**. Toda nova feature, alteração arquitetural ou grande refatoração deve começar aqui, antes do código.

## A Estrutura `.spec/`

- **`domains/`**: Agrupa as especificações por área funcional do produto (ex: `studio`, `pipeline`, `blog`, `portfolio`, `security`, `infra`).
  - `requirements.md`: O que o sistema deve fazer (Casos de Uso / Histórias).
  - `design.md`: Como o sistema fará (Arquitetura, Modelos de Dados).
  - `decisions.md`: Registro de decisões importantes (ADRs).
  - `tasks.md`: Lista de tarefas pendentes e acompanhamento.
  - `status.md`: Estado atual da implementação.
- **`workflows/`**: Processos para o ciclo de vida de desenvolvimento (ex: deploy, desenvolvimento local).

## Workflow

1. **Antes de codar**: Atualize `requirements.md` e `design.md` no domínio relevante.
2. **Durante o código**: Acompanhe e atualize as tarefas em `tasks.md`.
3. **Após concluir**: Garanta que as decisões arquiteturais estão em `decisions.md` e o `status.md` reflete o estado final.
