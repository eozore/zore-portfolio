---
trigger: model_decision
description: Regras para a Ferramenta de Gestão de Conteúdo (Content Tool)
---

# Regras e Arquitetura Mestre do CSM Studio (Content Strategy Machine)

Ao desenvolver, manter ou evoluir a suíte de criação de conteúdo `admin/csm`, o agente deve seguir **ESTRITAMENTE** as especificações de UX, Filosofia e Fluxo de Dados definidas no documento raiz oficial:

👉 [Consultar Blueprint Mestre: build_csm_tool.md](../../build_csm_tool.md)

### Destaques Fundamentais:
1. **Dinámica Executiva:** O usuário atua como **CEO** direcionando a pauta e a IA atua como **Diretor de Marketing (CMO) crítico**.
2. **Artefato Único Primário:** A concepção na Aba 1 gera exclusivamente **Artigos de Blog educacionais profundos**. Não apresente seletores de formatos alternativos na criação primária.
3. **Artigos Ricos:** O redator deve incluir fórmulas LaTeX e diagramas arquiteturais ` ```mermaid ` além de tabelas GFM.
4. **Derivação & Calendário:** A derivação omnicanal na Aba 4 gera massivamente peças para LinkedIn, YouTube, Reels, Carrosseis e Stories. Apenas itens marcados como `🟢 Aprovado` no calendário editorial vão para o banco de dados.