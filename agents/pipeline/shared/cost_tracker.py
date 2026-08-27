"""
agents/pipeline/shared/cost_tracker.py
========================================
Rastreamento e gate de custo da content pipeline éozoré.

Taxas de API (referência):
  ElevenLabs:            $0.00005/char
  HeyGen:                depende do MOTOR — ver USD_POR_MINUTO_POR_MOTOR

A taxa USD→BRL é lida do Firestore pipeline_config/{tenant_id}.
Nunca hardcoded exceto como fallback de default (5.50).
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


class TenantBudgetExceededError(Exception):
    """
    O tenant ultrapassaria o teto mensal configurado em
    pipeline_config/{tenant_id}.monthly_budget_brl.

    Diferente de CostGateBlockedError (que existe hoje por projeto), este gate
    é por TENANT e olha o mês inteiro — impede que N produções pequenas,
    nenhuma delas violando o teto por projeto sozinha, somem mais do que o
    tenant autorizou gastar no período.
    """

# Taxas de API (USD)
ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR: float = 0.00005   # $0.00005/char

# Custo por caractere, por modelo da ElevenLabs. Flash bota metade de um
# crédito por caractere; multilingual_v2 bota um inteiro — o dobro. Como o
# TTS trocou de Flash para multilingual_v2 (Flash só ganha em latência, que
# num pipeline batch não vale nada), estimar tudo com a tarifa do Flash
# passaria a subestimar o custo pela metade.
USD_POR_CHAR_POR_MODELO: dict[str, float] = {
    "eleven_flash_v2_5":     ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR,
    "eleven_turbo_v2_5":     ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR,
    "eleven_multilingual_v2": ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR * 2,
}

# Modelo desconhecido cai no mais caro, pelo mesmo motivo do motor do HeyGen:
# subestimar custo desarma o gate em vez de acioná-lo.
USD_POR_CHAR_PADRAO: float = max(USD_POR_CHAR_POR_MODELO.values())

# Preço por MINUTO de vídeo gerado, por motor de renderização do HeyGen.
#
# A constante anterior era única — $0.0335/s, ou $2,01/min — e não batia com
# nenhum preço do avatar: $2/min é a tarifa de *video translation* e do Video
# Agent, produtos que esta pipeline não usa. O gate estimava o dobro do custo
# real do avatar padrão.
#
# Confirmado em developers.heygen.com/docs/pricing (consultado em 27/08/2026).
# `avatar_v` deixou de ser presunção: a HeyGen publica US$4,00/min, que é o
# valor que já estava aqui. O job continua MEDINDO o custo real pela variação
# do saldo a cada produção (ver AvatarJob._saldo_usd) — a tabela é estimativa
# de gate, a medição é o número verdadeiro.
#
# A tabela publicada tem FAIXA, não valor único: III custa US$1,00–2,60/min e
# IV custa US$3,00–4,00/min, conforme o tipo de avatar. Os valores abaixo são
# os do avatar padrão (III) e o teto (IV). Se algum dia um avatar de tipo mais
# caro entrar em uso no III, esta linha subestima — e subestimar custo desarma
# o gate.
USD_POR_MINUTO_POR_MOTOR: dict[str, float] = {
    "avatar_iii": 1.0,   # avatar padrão, 720p/1080p (faixa vai até 2,60)
    "avatar_iv":  4.0,   # teto da faixa 3,00–4,00, em 1080p
    "avatar_v":   4.0,   # publicado, Digital Twins
}

# Motor desconhecido cai no mais caro: subestimar custo desarma o gate.
USD_POR_MINUTO_PADRAO: float = max(USD_POR_MINUTO_POR_MOTOR.values())


def usd_por_segundo(engine: str) -> float:
    """Preço por segundo de vídeo para o motor, sobrescrevível por env."""
    override = os.environ.get("HEYGEN_USD_PER_MINUTE", "").strip()
    if override:
        try:
            return float(override) / 60.0
        except ValueError:
            logger.warning("[cost] HEYGEN_USD_PER_MINUTE inválido: %r", override)
    return USD_POR_MINUTO_POR_MOTOR.get(engine, USD_POR_MINUTO_PADRAO) / 60.0


# Mantido para quem ainda importa o nome antigo. Aponta para o motor em uso.
HEYGEN_SPEED_RATE_USD_PER_SECOND: float = usd_por_segundo(
    os.environ.get("HEYGEN_ENGINE", "avatar_v")
)


class CostTrackerService:
    """
    Rastreia custo acumulado por projeto e verifica gates de custo.

    Taxa de câmbio USD→BRL é lida do Firestore pipeline_config.exchange_rate_usd_brl.
    Nunca hardcoded — permite ajuste sem redeploy.
    """

    def __init__(self, firestore: Any, tenant_id: str = "default") -> None:
        self.firestore = firestore
        self.tenant_id = tenant_id
        self._exchange_rate: float | None = None

    async def _get_exchange_rate(self) -> float:
        """Lê taxa de câmbio do Firestore. Cache por instância (lifetime do Job)."""
        if self._exchange_rate is None:
            config = await self.firestore.get_pipeline_config(self.tenant_id)
            self._exchange_rate = config.get("exchange_rate_usd_brl", 5.50)
        return self._exchange_rate

    async def estimate_tts_cost(
        self,
        chars: int,
        model: str | None = None,
    ) -> float:
        """
        Estima custo TTS em BRL.

        Args:
            chars: Número de caracteres a processar
            model: Modelo ElevenLabs; None usa o configurado no ambiente

        Returns:
            Custo estimado em BRL (float)

        Antes isto levantava ValueError para qualquer modelo diferente de
        `eleven_flash_v2_5`. Recusar o cálculo derruba a produção inteira por
        causa de uma ESTIMATIVA — o gate existe para barrar gasto, não para
        virar ponto de falha quando alguém troca de modelo.
        """
        nome = model or os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        por_char = USD_POR_CHAR_POR_MODELO.get(nome)
        if por_char is None:
            logger.warning(
                "[cost] Modelo ElevenLabs desconhecido (%s) — usando a tarifa mais "
                "alta para não subestimar.", nome,
            )
            por_char = USD_POR_CHAR_PADRAO
        cost_usd = chars * por_char
        rate = await self._get_exchange_rate()
        return round(cost_usd * rate, 4)

    async def estimate_heygen_cost(
        self, duration_s: float, engine: str | None = None,
    ) -> float:
        """
        Estima o custo da geração de avatar em BRL.

        Args:
            duration_s: Duração total do áudio em segundos
            engine:     Motor do HeyGen; None usa o configurado no ambiente

        Returns:
            Custo estimado em BRL (float)
        """
        motor = engine or os.environ.get("HEYGEN_ENGINE", "avatar_v")
        cost_usd = duration_s * usd_por_segundo(motor)
        rate = await self._get_exchange_rate()
        return round(cost_usd * rate, 4)

    async def check_cost_gate(
        self,
        project_id: str,
        additional_cost: float,
        limit: float,
    ) -> bool:
        """
        Verifica se (custo_atual + additional_cost) <= limit.

        Se False: escreve cost_blocked no Firestore imediatamente.

        Args:
            project_id:      ID do projeto
            additional_cost: Custo adicional estimado em BRL (próxima etapa)
            limit:           Teto de custo em BRL (de pipeline_config.cost_limit)

        Returns:
            True se pode prosseguir, False se custo excederia o teto
        """
        project = await self.firestore.get_project(project_id)
        cost_breakdown: dict[str, Any] = project.get("cost_breakdown", {})
        current_cost: float = cost_breakdown.get("total_real", 0.0)

        if current_cost + additional_cost > limit:
            logger.warning(
                "[CostGate] BLOQUEADO project=%s: "
                "atual=%.2f + estimado=%.2f > limite=%.2f BRL",
                project_id,
                current_cost,
                additional_cost,
                limit,
            )
            await self.firestore.update_project(
                project_id,
                {
                    "cost_blocked": {
                        "blocked": True,
                        "current_cost": current_cost,
                        "estimated_next": additional_cost,
                        "limit": limit,
                        "blocked_at": int(time.time()),
                    }
                },
            )
            return False

        return True

    async def update_actual_cost(
        self,
        project_id: str,
        stage: str,
        cost_usd: float,
    ) -> None:
        """
        Registra custo real de uma etapa após execução.

        Converte USD → BRL usando taxa de câmbio do Firestore.
        Atualiza cost_breakdown.{stage} e recalcula total_real.

        Args:
            project_id: ID do projeto
            stage:      "tts" | "heygen" | "gemini" | "gcp"
            cost_usd:   Custo real da etapa em USD
        """
        rate = await self._get_exchange_rate()
        cost_brl = round(cost_usd * rate, 4)

        project = await self.firestore.get_project(project_id)
        breakdown: dict[str, Any] = dict(project.get("cost_breakdown", {}))
        breakdown[stage] = round((breakdown.get(stage) or 0.0) + cost_brl, 4)

        # Recalcula total_real a partir das quatro categorias
        tts    = breakdown.get("tts")    or 0.0
        heygen = breakdown.get("heygen") or 0.0
        gemini = breakdown.get("gemini") or 0.0
        gcp    = breakdown.get("gcp")    or 0.0
        breakdown["total_real"] = round(tts + heygen + gemini + gcp, 4)

        await self.firestore.update_project(project_id, {"cost_breakdown": breakdown})
        logger.info(
            "[CostTracker] project=%s stage=%s cost_usd=%.6f cost_brl=%.4f total_brl=%.4f",
            project_id,
            stage,
            cost_usd,
            cost_brl,
            breakdown["total_real"],
        )

        # Único choke point de gasto REAL (não estimado) na pipeline hoje —
        # todo `update_actual_cost` também soma no mês corrente do tenant.
        # HeyGen não passa por aqui (avatar_job nunca registra custo real,
        # só a estimativa pré-voo — ver record_tenant_spend_estimate), então o
        # mês do tenant hoje é preciso para TTS e otimista para avatar.
        await self.record_tenant_spend(cost_brl)

    # ── Quota mensal por tenant ──────────────────────────────────────────────
    #
    # Independente do gate por projeto acima (check_cost_gate): aquele olha
    # SÓ este projeto; este olha o mês inteiro do tenant. Um tenant pode nunca
    # estourar o teto de um projeto e ainda assim exceder o orçamento mensal
    # produzindo muitos projetos pequenos.

    async def check_tenant_budget(self) -> bool:
        """
        True se o tenant pode prosseguir. False se o mês já estourou o teto.

        Sem `monthly_budget_brl` configurado em pipeline_config/{tenant_id} →
        sempre True — nenhum tenant é bloqueado por um limite que ninguém
        definiu. É o comportamento de hoje, preservado.
        """
        config = await self.firestore.get_pipeline_config(self.tenant_id)
        budget = config.get("monthly_budget_brl")
        if budget is None:
            return True

        month = _current_month()
        spent = await self.firestore.get_tenant_monthly_spend(self.tenant_id, month)
        if spent >= float(budget):
            logger.warning(
                "[TenantBudget] BLOQUEADO tenant=%s mês=%s: gasto=%.2f >= teto=%.2f BRL",
                self.tenant_id, month, spent, budget,
            )
            return False
        return True

    async def record_tenant_spend(self, amount_brl: float) -> None:
        """
        Soma ao gasto do tenant no mês corrente.

        Ignora valores <= 0 aqui mesmo, antes de chamar o Firestore — evita um
        round-trip de rede para um incremento que não muda nada, e mantém a
        garantia mesmo se `firestore` for um wrapper mais simples que não
        repita a checagem.
        """
        if amount_brl <= 0:
            return
        await self.firestore.add_tenant_spend(self.tenant_id, _current_month(), amount_brl)

    async def record_tenant_spend_estimate_usd(self, cost_usd: float) -> None:
        """
        Registra uma ESTIMATIVA de gasto (usada pelo HeyGen, cujo custo real
        nunca é reportado de volta pela API — só o pré-voo é calculável).
        Mesma conversão USD→BRL do resto do serviço.

        É melhor um teto mensal otimista do que nenhum: sem isto, o gasto
        dominante da pipeline (HeyGen) nunca entraria na conta do tenant.
        """
        rate = await self._get_exchange_rate()
        await self.record_tenant_spend(round(cost_usd * rate, 4))
