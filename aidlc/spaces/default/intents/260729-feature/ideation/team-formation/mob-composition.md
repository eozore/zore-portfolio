# Mob Composition

Projeto solo — não aplicável como mob programming formal.

## Approach: Driver + Navigator assíncrono
- **Navigator (Victor):** Define o problema, aprova artefatos, testa em produção
- **Driver (Kiro AI):** Escreve o código, executa comandos, lê arquivos, verifica erros

## Handoff por bug
Cada bug é implementado e verificado localmente antes de avançar para o próximo. Deploy em produção após todos os bugs de uma sessão estarem estáveis.
