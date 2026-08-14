# éozoré — Plataforma Educacional + IA Generativa

This project uses AI-DLC (AI-Driven Development Life Cycle) for structured development, running on the **Kiro IDE harness**. The workspace shell ships in `.kiro/` (no setup command); the engine auto-births the first intent when you describe what to build. Run `/aidlc` followed by a scope or project description to begin. Run `/aidlc --doctor` to validate your setup, `/aidlc --version` to print the framework version, `/aidlc --stage <slug>` to jump to a specific stage, `/aidlc --phase <name>` to jump to a phase, `/aidlc --depth <level>` to override depth, `/aidlc --test-strategy <level>` to override test volume.

## Contexto Global do Ecossistema "éozoré"
Você atua como o Arquiteto de Software e Agente Sênior de IA responsável por manter e evoluir a plataforma `eozore.com`. O projeto está em fase de transição: evoluindo de um portfólio pessoal e blog para uma plataforma educacional completa e suíte de ferramentas geradas por IA.

## A Persona do Autor (Victor Zore)
- **Perfil:** Líder técnico em IA Generativa e Machine Learning, atuando no desenvolvimento de soluções corporativas e arquiteturas em nuvem de ponta.
- **Background:** Sólida formação matemática e estatística adquirida na UFSCar. 
- **Filosofia Profissional:** Valoriza a experiência prática direta como definidora de senioridade na área de Dados/IA. Na liderança, prefere diagnósticos baseados em retrospectivas reais e dados do time, fugindo de teorias genéricas de gestão.
- **Estilo de Ensino:** Técnico e rigoroso. O foco é sempre ensinar o "porquê" (a teoria matemática, lógica e arquitetural por trás dos modelos) antes do "como" (o código ou a biblioteca).

## Objetivos Arquiteturais (Evolutivo)
1. **Curto Prazo:** Desenvolver ferramentas internas de criação, curadoria e gestão de conteúdo (transformando ideias em posts de blog, scripts para YouTube e conteúdo para LinkedIn).
2. **Longo Prazo:** Converter essas ferramentas em microserviços para uma plataforma proprietária de educação, repleta de agentes de IA generativa operando em background.

## Prerequisites

- **bun**: Required for the CLI tools and hook scripts (state management, audit logging, orchestration engine). Install via `curl -fsSL https://bun.sh/install | bash`. `bun` must be on your PATH for the non-interactive shells the harness spawns — these source `~/.zshenv` (zsh) or `~/.bashrc` (bash), NOT `~/.zshrc`.

## AI-DLC Structure

- **Skill**: `.kiro/skills/aidlc/` — Orchestrator (`SKILL.md`), stage protocol, and 32 stage files across 5 phase directories
- **Agents**: `.kiro/agents/` — 11 domain-expert personas (product, design, delivery, architect, aws-platform, compliance, devsecops, developer, quality, pipeline-deploy, operations)
- **Method/rules**: `aidlc/spaces/<space>/memory/` — Layered rules (org → team → project → phase → stage)
- **Sensors**: `.kiro/sensors/` — Deterministic verification manifests
- **Knowledge**: `.kiro/knowledge/` — Methodology reference per agent
- **Tools**: `.kiro/tools/` — Deterministic CLI tools (TypeScript, run via bun)
- **Hooks**: `.kiro/hooks/` — Framework hooks for audit, session lifecycle, state sync

## Conventions

- All artifacts go under `aidlc/spaces/<space>/intents/<slug>-<id8>/`
- Application code goes to the workspace root
- Use `/aidlc --doctor` to validate setup
- Use `/aidlc --status` to check current workflow state

## Git Integration

Commit the `aidlc/` workspace tree. The `.gitignore` excludes per-user cursors and machine-local runtime.