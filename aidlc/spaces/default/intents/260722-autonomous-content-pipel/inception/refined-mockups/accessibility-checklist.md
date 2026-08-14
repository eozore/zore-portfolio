# Accessibility Checklist
## Pipeline Autônoma de Conteúdo Omnicanal éozoré

> WCAG 2.1 AA. Referências: [wireframes.md](../../ideation/rough-mockups/wireframes.md) | [stories.md](../user-stories/stories.md) | [requirements.md](../requirements-analysis/requirements.md) | [team-practices.md](../practices-discovery/team-practices.md)
> **Nota:** Validação completa de conformidade WCAG requer testes manuais com tecnologias assistivas e revisão especializada em acessibilidade.

---

## 1. Estrutura Semântica e Landmarks

| Componente | Requisito | Implementação |
|---|---|---|
| `CsmDashboard` — tab bar | `role="tablist"`, cada aba com `role="tab"` | Navegação setas ←/→ entre abas |
| `ProjectsTab` — heading | `h1` "Projetos de Conteúdo" | Apenas 1 h1 por view |
| `ProjectCard` — heading | `h3` para título do projeto | Hierarquia h1 > h3 (sem h2 entre eles no card) |
| `ProjectDetailPanel` | `role="dialog"`, `aria-modal="true"` | `aria-labelledby` aponta para h2 do panel |
| `ApprovalModal` | `role="dialog"`, `aria-modal="true"` | `aria-labelledby` aponta para h2 |
| `PipelineTab` | Seções com `h2` | "Canais", "APIs Externas", "Limites", "Agenda" |
| Filtros do kanban | `role="tablist"` | `aria-selected` no filtro ativo |

---

## 2. Contraste de Cores

| Elemento | Cor foreground | Cor background | Ratio Estimado | WCAG AA |
|---|---|---|---|---|
| Texto principal | `#f8fafc` | `rgba(10,10,20,0.98)` | ~18:1 | ✅ Pass |
| Texto secundário | `#94a3b8` | dark | ~7:1 | ✅ Pass |
| Status badge texto | branco | badge color | verificar por cor | ⚠ Verificar âmbar |
| Custo estimado | `#f59e0b` âmbar | dark | ~5.7:1 | ✅ Pass |
| Texto erro | `#ef4444` | dark | ~4.8:1 | ✅ Pass (AA) |
| Link de ajuda | `#06b6d4` cyan | dark | ~6.2:1 | ✅ Pass |

> ⚠ O badge âmbar (`#f59e0b` sobre `#f59e0b` background) requer text branco (#fff) para garantir contraste adequado. Verificar em implementação.

---

## 3. Navegação por Teclado

| Componente | Teclas de Suporte | Comportamento |
|---|---|---|
| Tab bar | `←` `→` | Move entre abas; `Enter`/`Space` ativa |
| ProjectCard | `Enter`/`Space` | Abre side panel |
| ProjectCard CTA | `Tab` para focar, `Enter` para ativar | — |
| Filtros do kanban | `←` `→` | Navega filtros como radiogroup |
| ProjectDetailPanel | `Esc` | Fecha o panel; foco volta ao card que o abriu |
| ApprovalModal | `Esc` | Fecha o modal; foco volta ao botão "Aprovar" |
| Focus trap | — | Foco preso em modal/panel enquanto abertos |
| ApiKeyField "Editar" | `Enter` | Ativa modo de edição; foco move para o input |
| Diálogo de confirmação "Pular" | `Tab` navega "Cancelar"/"Pular"; `Esc` cancela | — |

---

## 4. ARIA Labels e Roles

### ProjectCard
```html
<article
  role="article"
  aria-label="{título}, status: {status label}"
>
  <!-- Badge -->
  <span role="status" aria-live="polite" aria-label="Status: {label}">
    {status text}
  </span>

  <!-- CostMeter -->
  <div
    role="progressbar"
    aria-valuenow="{custo_real}"
    aria-valuemin="0"
    aria-valuemax="{limite}"
    aria-label="Custo: R${custo_real} de R${limite}"
  />

  <!-- CTA primário -->
  <button aria-label="{CTA label} para {título do projeto}">
    {CTA text}
  </button>
</article>
```

### ApiKeyField
```html
<label for="key-elevenlabs">ElevenLabs API Key</label>
<input
  id="key-elevenlabs"
  type="password"
  autocomplete="off"
  aria-describedby="key-elevenlabs-help"
  placeholder="Cole a nova API key aqui"
/>
<div id="key-elevenlabs-help" class="sr-only">
  Este campo nunca é pré-preenchido. Cole a nova chave para substituir.
</div>
```

### Toggles de Canal
```html
<button
  role="switch"
  aria-checked="{enabled}"
  aria-label="YouTube publicação {enabled ? 'habilitada' : 'desabilitada'}"
>
```

### Status de Ping
```html
<!-- Anunciado automaticamente quando muda -->
<div role="status" aria-live="polite" aria-atomic="true">
  {status text, ex: "ATIVO (189ms)" ou "INATIVO — Erro 401"}
</div>
```

---

## 5. Estados de Foco Visíveis

```css
/* Padrão global para todos os componentes focáveis */
:focus-visible {
  outline: 2px solid #7c3aed;
  outline-offset: 2px;
  border-radius: 4px;
}

/* Nunca usar outline: none sem alternativa */
```

---

## 6. Conteúdo Dinâmico (Live Regions)

| Elemento | `aria-live` | Comportamento |
|---|---|---|
| Status badge do card | `polite` | Anuncia mudança de estado ao completar um job |
| Toast notifications | `assertive` | Anuncia imediatamente (erros críticos) |
| Status do ping de API | `polite` | Anuncia resultado após teste |
| Retry count no side panel | `polite` | Anuncia "Tentativa 2 de 3" |
| Custo atualizado | `polite` | Anuncia quando custo real é registrado |

---

## 7. Formulários e Inputs

| Componente | Requisito |
|---|---|
| `ApiKeyField` | `<label>` associado via `for`/`id`; `aria-describedby` para ajuda contextual |
| Date picker no `PublishModal` | `type="datetime-local"` com label explícito; exibição do fuso horário em texto |
| Checkboxes de canais | `<label>` com texto do canal; grupo com `<fieldset>` + `<legend>` "Canais de publicação" |
| Radio buttons "Publicar agora / Agendar" | `<fieldset>` + `<legend>` "Quando publicar" |
| Campos numéricos (teto de custo, max/dia) | `type="number"` com `min`, `max`; unidade no label ("R$", "posts") |

---

## 8. Checklist de Verificação Pré-Deploy

> ⚠ Itens marcados com `[ ]` requerem verificação manual com tecnologias assistivas. Validação completa requer testes com VoiceOver (macOS/iOS) e NVDA/JAWS (Windows).

- [ ] Navegar toda a aba "Projetos" apenas com teclado (sem mouse)
- [ ] Abrir/fechar side panel e modais com teclado
- [ ] Focus trap funcionando em ApprovalModal e PublishModal
- [ ] Todos os status badges anunciados pelo VoiceOver ao mudar
- [ ] CostMeter progressbar com valores corretos no aria-valuenow
- [ ] ApiKeyField: input vazio ao entrar em modo edit (sem pré-preenchimento)
- [ ] Toast notifications anunciadas pelo screen reader
- [ ] Contraste do badge âmbar verificado em implementação real
- [ ] Todos os toggles de canal anunciam estado corretamente
- [ ] Formulário de configuração navega por tab em ordem lógica
