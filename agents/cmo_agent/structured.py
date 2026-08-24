# -*- coding: utf-8 -*-
"""
structured.py — Saída estruturada garantida pelo Vertex.

Converte um modelo Pydantic no `responseSchema` que o Vertex aceita e chama o
modelo com ele. O decoder do Gemini passa a ser obrigado a emitir JSON válido
contra o schema: não existe markdown na frente, prosa no meio nem vírgula
sobrando no fim.

Por que existe: até aqui todo agente fazia o mesmo ritual — pedir JSON no
prompt, tirar ```json com regex, remover <think>, e por último tentar
`re.sub(r",\\s*([}\\]])", r"\\1", raw)` para consertar vírgula extra. É um
parser de JSON escrito em expressão regular. Foi por uma falha dessa classe
que um manifesto quebrado passou adiante e virou um vídeo de 163 segundos de
avatar puro.

O Vertex não aceita JSON Schema completo. O subconjunto suportado é o do
OpenAPI 3.0, e alguns construtos que o Pydantic emite naturalmente quebram a
chamada — por isso `to_vertex_schema()` existe em vez de um
`model_json_schema()` direto.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("cmo_agent.structured")

T = TypeVar("T", bound=BaseModel)

# Chaves que o Vertex rejeita ou ignora silenciosamente no responseSchema.
# `additionalProperties` e `$schema` causam erro 400; `default` e `examples`
# são aceitos mas inflam o schema sem efeito no decoder.
_UNSUPPORTED_KEYS = {
    "additionalProperties", "$schema", "default", "examples",
    "discriminator", "readOnly", "writeOnly", "xml", "externalDocs",
    "const", "patternProperties", "definitions",
}


# Regra de ortografia prefixada em toda geração estruturada.
#
# Medido: com responseSchema ativo, o modelo passa a devolver português SEM
# ACENTO com frequência ("Nao confie", "predicoes", "producao") — o decoder
# restrito parece empurrar a saída para ASCII. O mesmo prompt sem schema sai
# acentuado. Como isto vai direto para post publicado, a regra é explícita.
PT_BR_ORTOGRAFIA = (
    "━━━ ESCRITA EM PORTUGUÊS (regras inegociáveis) ━━━\n"
    "1. ACENTUAÇÃO COMPLETA: á é í ó ú â ê ô ã õ à ç. Escrever "
    "'producao' ou 'e o erro' em vez de 'produção' e 'é o erro' é erro de "
    "português, e o texto será rejeitado.\n"
    "2. SIGLAS EM MAIÚSCULA, sempre: IA, LLM, RAG, GCP, API, A/B, ML. "
    "Sentence case vale para a FRASE, não para siglas — 'testes a/b com ia' "
    "está errado; 'testes A/B com IA' está certo.\n"
    "3. Títulos em sentence case: só a primeira letra maiúscula, mais nomes "
    "próprios e siglas. Nunca Title Case — 'Por que Testes A/B são "
    "Inegociáveis' está errado; 'Por que testes A/B são inegociáveis' está "
    "certo.\n"
    "4. Slugs em português, sem acento, separados por hífen: "
    "'testes-ab-ia-generativa', nunca 'ab-testing-generative-ai'."
)


class StructuredOutputError(RuntimeError):
    """O modelo devolveu JSON que não valida contra o schema pedido."""


def _resolve_refs(node: Any, defs: dict) -> Any:
    """
    Achata `$ref`/`$defs` do Pydantic.

    O Vertex não resolve referências: um schema com `$ref` chega ao decoder
    como um objeto vazio, e o modelo devolve `{}` para aquele campo — sem erro
    nenhum, só um campo faltando no resultado.
    """
    if isinstance(node, list):
        return [_resolve_refs(n, defs) for n in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        ref_name = node["$ref"].rsplit("/", 1)[-1]
        target = defs.get(ref_name)
        if target is None:
            logger.warning("[structured] $ref não resolvido: %s", node["$ref"])
            return {"type": "string"}
        merged = _resolve_refs(dict(target), defs)
        # Um $ref pode vir acompanhado de description no mesmo nível.
        for k, v in node.items():
            if k != "$ref":
                merged[k] = v
        return merged

    out: dict = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYS:
            continue
        # anyOf com null é como o Pydantic representa Optional[...]. O Vertex
        # não suporta anyOf; colapsa no primeiro tipo não-nulo e marca como
        # não-obrigatório (o campo já sai de `required` no Pydantic).
        if key == "anyOf" and isinstance(value, list):
            non_null = [v for v in value if v.get("type") != "null"]
            if non_null:
                collapsed = _resolve_refs(non_null[0], defs)
                out.update({k: v for k, v in collapsed.items() if k not in out})
            continue
        out[key] = _resolve_refs(value, defs)
    return out


# Teto por descrição de campo. O decoder usa a descrição como orientação, não
# como documentação — texto longo demais rouba espaço sem mudar o resultado.
MAX_DESCRICAO = 180


def _enxugar(node: Any, raiz: bool = True) -> Any:
    """
    Remove peso morto do schema antes de mandar ao Vertex.

    Descoberto na prática: o `PlanoSocial` inteiro dava HTTP 400
    ("invalid argument") enquanto cada peça isolada passava. A causa era
    TAMANHO — 11,5 KB, dos quais 48% eram descrição, com a docstring da classe
    CTA repetida quatro vezes por estar aninhada em cada tipo de peça.

    Duas podas, nesta ordem de importância:
      1. A `description` de OBJETO (que vem da docstring da classe) sai. Ela
         documenta o código para quem lê, não orienta o decoder.
      2. Descrição de CAMPO é truncada — essa sim guia a geração, mas não
         precisa de parágrafo.

    `title` também sai: o Pydantic gera um para cada campo e nenhum é lido.
    """
    if isinstance(node, list):
        return [_enxugar(n, False) for n in node]
    if not isinstance(node, dict):
        return node

    out: dict = {}
    for key, value in node.items():
        if key == "title":
            continue
        if key == "description" and isinstance(value, str):
            # Objeto (docstring de classe) perde a descrição; campo mantém,
            # cortado na fronteira de frase para não truncar no meio.
            if node.get("type") == "object":
                continue
            if len(value) > MAX_DESCRICAO:
                corte = value[:MAX_DESCRICAO]
                ponto = corte.rfind(". ")
                value = (corte[: ponto + 1] if ponto > MAX_DESCRICAO * 0.4 else corte).strip()
            out[key] = value
            continue
        out[key] = _enxugar(value, False)
    return out


def to_vertex_schema(model: Type[BaseModel]) -> dict:
    """Modelo Pydantic → responseSchema aceito pelo Vertex."""
    raw  = model.model_json_schema()
    defs = raw.get("$defs", {})
    schema = _resolve_refs(raw, defs)
    schema.pop("$defs", None)
    return _enxugar(schema)


async def generate_structured(
    model: Type[T],
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.5,
    repair_attempts: int = 1,
    ortografia_pt_br: bool = True,
) -> T:
    """
    Gera e valida uma resposta contra `model`.

    O schema garante JSON sintaticamente válido; a validação do Pydantic
    garante que ele é SEMANTICAMENTE o que pedimos (campos obrigatórios,
    limites de tamanho, enums). As duas coisas são necessárias: o decoder do
    Vertex respeita a forma, não as regras de negócio.

    Em falha de validação faz uma nova tentativa devolvendo os erros ao
    modelo. Uma só — se o modelo não acerta com o erro na mão, insistir é
    queimar token.
    """
    from vertex_generate import generate_text

    if ortografia_pt_br:
        # No INÍCIO, não no fim. Medido no ambiente local: com o catálogo de
        # skills a instrução passa de 5.000 caracteres, e a regra anexada no
        # fim se dilui — o plano social saiu com 0,3% de acentuação contra
        # 2,6% do artigo, que usa outro caminho. Instrução de forma vai na
        # frente; instrução de conteúdo, depois.
        system_instruction = f"{PT_BR_ORTOGRAFIA}\n\n{system_instruction}".strip()

    schema = to_vertex_schema(model)
    raw = await generate_text(
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        response_schema=schema,
    )

    for attempt in range(repair_attempts + 1):
        try:
            return model.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            if attempt >= repair_attempts:
                logger.error(
                    "[structured] %s não validou após %d tentativa(s): %s",
                    model.__name__, attempt + 1, str(exc)[:400],
                )
                raise StructuredOutputError(
                    f"{model.__name__} inválido: {str(exc)[:300]}"
                ) from exc

            logger.warning(
                "[structured] %s inválido, devolvendo os erros ao modelo: %s",
                model.__name__, str(exc)[:200],
            )
            raw = await generate_text(
                prompt=(
                    f"{prompt}\n\n"
                    f"=== A RESPOSTA ANTERIOR FOI REJEITADA ===\n"
                    f"{str(exc)[:1500]}\n\n"
                    f"Corrija EXATAMENTE esses erros. Mantenha todo o resto igual."
                ),
                system_instruction=system_instruction,
                temperature=temperature,
                response_schema=schema,
            )

    raise StructuredOutputError("inalcançável")
