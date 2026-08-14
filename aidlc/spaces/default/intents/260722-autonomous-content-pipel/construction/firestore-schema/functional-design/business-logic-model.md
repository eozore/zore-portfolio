# Business Logic Model — U-01: firestore-schema

> Referências: [unit-of-work.md](../../../inception/units-generation/unit-of-work.md) | [requirements.md](../../../inception/requirements-analysis/requirements.md) | [components.md](../../../inception/application-design/components.md) | [component-methods.md](../../../inception/application-design/component-methods.md) | [services.md](../../../inception/application-design/services.md) | [unit-of-work-story-map.md](../../../inception/units-generation/unit-of-work-story-map.md)

---

## Escopo

U-01 é a unidade de fundação — sem lógica de negócio própria. Provê os contratos de dados que todos os outros jobs e o frontend consomem. O "business logic" aqui são as **regras de validação de schema** e a **garantia de consistência** entre os tipos TypeScript e Python.

## Ficheiros a Criar

```
apps/web/src/types/
  pipeline.ts          ← tipos TypeScript (domain-entities.md)

agents/pipeline/
  shared/
    models.py          ← dataclasses Python (domain-entities.md)
    __init__.py        ← exports

firestore.rules        ← na raiz do projeto
firestore.indexes.json ← na raiz do projeto
```

## Validação de Schema — Algoritmo

```python
def validate_manifest_segment(segment: dict) -> list[str]:
    """Valida um segmento do manifesto. Retorna lista de erros (vazia = válido)."""
    errors = []
    
    if not segment.get("id"):
        errors.append("segment.id é obrigatório")
    
    has_script = bool(segment.get("script"))
    has_slide  = segment.get("slide") is not None
    
    # BR-04: todo segmento deve ter script ou slide
    if not has_script and not has_slide:
        errors.append(f"Segmento {segment.get('id')}: deve ter script ou slide")
    
    # BR-05: min_duration_s obrigatório para slide puro
    if not has_script and has_slide:
        if not segment.get("min_duration_s"):
            errors.append(f"Segmento {segment.get('id')}: min_duration_s obrigatório para slide puro")
    
    return errors
```

## Deploy dos Artefatos de Infra

```bash
# Deploy das regras Firestore
firebase deploy --only firestore:rules --project vazfy-417019

# Deploy dos índices Firestore
firebase deploy --only firestore:indexes --project vazfy-417019
```

**Nota:** os índices podem levar até 10 minutos para ficar ativos. O índice `collection_group` em `lipsync_jobs.lipsync_id` é crítico — sem ele o HeyGenCallbackHandler falha com erro 400.

## Teste Nyquist (1 teste)

```typescript
// apps/web/src/types/pipeline.test.ts
import { ContentProject, ProjectStatus, StageStatus } from './pipeline';

describe('ContentProject schema', () => {
  it('aceita um projeto válido com todas as etapas', () => {
    const project: ContentProject = {
      id: 'test-123',
      title: 'Test Project',
      status: 'awaiting_approval',
      manifest_url: 'gs://bucket/projects/test-123/manifest.html',
      created_at: Date.now(),
      created_by: 'victor',
      stages: {
        tts:       { id: 'tts',       label: 'TTS Audio',    status: 'pending', retry_count: 0, max_retries: 3 },
        avatar:    { id: 'avatar',    label: 'Avatar Video', status: 'pending', retry_count: 0, max_retries: 3 },
        editor:    { id: 'editor',    label: 'Video Editor', status: 'pending', retry_count: 0, max_retries: 3 },
        publisher: { id: 'publisher', label: 'Publisher',    status: 'pending', retry_count: 0, max_retries: 3 },
      },
      cost_breakdown: { total_real: 0, total_estimated: 67 },
    };
    // TypeScript compile-time check — se compilar, o tipo está correto
    expect(project.status).toBe('awaiting_approval');
  });
});
```
