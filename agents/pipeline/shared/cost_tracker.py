"""
agents/pipeline/shared/cost_tracker.py
========================================
Rastreamento e gate de custo da content pipeline éozoré.

Taxas de API (referência):
  ElevenLabs Flash v2.5: $0.00005/char
  HeyGen Lipsync speed:  $0.0335/s

A taxa USD→BRL é lida do Firestore pipeline_config/{tenant_id}.
Nunca hardcoded exceto como fallback de default (5.50).
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Taxas de API (USD)
ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR: float = 0.00005   # $0.00005/char
HEYGEN_SPEED_RATE_USD_PER_SECOND: float = 0.0335            # $0.0335/s


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
        model: str = "eleven_flash_v2_5",
    ) -> float:
        """
        Estima custo TTS em BRL.

        Args:
            chars: Número de caracteres a processar
            model: Identificador do modelo ElevenLabs (apenas eleven_flash_v2_5 suportado)

        Returns:
            Custo estimado em BRL (float)

        Raises:
            ValueError: se model desconhecido
        """
        if model != "eleven_flash_v2_5":
            raise ValueError(
                f"Modelo desconhecido: {model}. Apenas eleven_flash_v2_5 suportado."
            )
        cost_usd = chars * ELEVENLABS_FLASH_V2_5_RATE_USD_PER_CHAR
        rate = await self._get_exchange_rate()
        return round(cost_usd * rate, 4)

    async def estimate_heygen_cost(self, duration_s: float) -> float:
        """
        Estima custo HeyGen Lipsync modo speed em BRL.

        Args:
            duration_s: Duração total do áudio em segundos

        Returns:
            Custo estimado em BRL (float)
        """
        cost_usd = duration_s * HEYGEN_SPEED_RATE_USD_PER_SECOND
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
