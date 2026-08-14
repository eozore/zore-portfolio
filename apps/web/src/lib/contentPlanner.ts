/**
 * contentPlanner.ts — Distribui os conteúdos aprovados de um projeto ao longo
 * dos próximos 7 dias, em horários de publicação fixos.
 *
 * Por que existe: antes da aprovação, todos os itens recebiam o MESMO
 * `scheduledAt` (agora + 24h), então o publisher horário despejava a campanha
 * inteira de uma vez na primeira execução — o oposto de uma campanha semanal.
 *
 * Como funciona:
 *   - O vídeo do YouTube é a âncora da semana e sai primeiro (D+1, manhã).
 *     Todo o resto aponta para ele, então nada social é agendado antes disso.
 *   - Os demais itens são distribuídos em rodízio pelos dias D+1..D+7,
 *     ocupando os slots de horário na ordem definida em PUBLISH_SLOTS_BRT.
 *   - Cada dia recebe no máximo PUBLISH_SLOTS_BRT.length itens, e a distribuição
 *     é intercalada por plataforma para não empilhar 3 posts de LinkedIn no
 *     mesmo dia enquanto o Instagram fica vazio.
 *
 * O publisher (Cloud Run Job `publisher-scheduled`, disparado pelo Cloud
 * Scheduler a cada hora em `0 * * * *`) já publica apenas os itens cujo
 * `scheduled_at` <= agora — então basta gravar as datas corretas aqui.
 */

/** Horários de publicação (hora local BRT). Ordem = prioridade de preenchimento. */
export const PUBLISH_SLOTS_BRT = [9, 12, 18];

/** Fuso de São Paulo em relação ao UTC (BRT = UTC-3, sem horário de verão desde 2019). */
const BRT_OFFSET_HOURS = 3;

export const PLAN_HORIZON_DAYS = 7;

export interface PlannableItem {
  platform: string;
  format: string;
  [key: string]: unknown;
}

export interface PlannedItem extends PlannableItem {
  scheduledAt: string;
  /** Dia do plano (1..7) — usado só para exibição no calendário. */
  planDay: number;
}

/**
 * Constrói um instante UTC para "daqui a `daysAhead` dias, às `hourBrt` no horário de Brasília".
 */
function slotToUtcIso(base: Date, daysAhead: number, hourBrt: number): string {
  const d = new Date(base);
  d.setUTCDate(d.getUTCDate() + daysAhead);
  d.setUTCHours(hourBrt + BRT_OFFSET_HOURS, 0, 0, 0);
  return d.toISOString();
}

/**
 * Intercala os itens por plataforma para espalhar os canais ao longo da semana,
 * em vez de publicar todos os posts de um mesmo canal em sequência.
 */
function interleaveByPlatform<T extends PlannableItem>(items: T[]): T[] {
  const buckets = new Map<string, T[]>();
  for (const item of items) {
    const key = item.platform || 'outros';
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key)!.push(item);
  }
  const queues = [...buckets.values()];
  const out: T[] = [];
  let moved = true;
  while (moved) {
    moved = false;
    for (const q of queues) {
      const next = q.shift();
      if (next) { out.push(next); moved = true; }
    }
  }
  return out;
}

/**
 * Distribui os itens ao longo dos próximos `PLAN_HORIZON_DAYS` dias.
 *
 * @param items itens aprovados (texto e/ou vídeo curto)
 * @param now   instante base — injetável para testes
 */
export function planWeek<T extends PlannableItem>(items: T[], now: Date = new Date()): (T & PlannedItem)[] {
  const ordered = interleaveByPlatform(items);
  const slotsPerDay = PUBLISH_SLOTS_BRT.length;

  return ordered.map((item, index) => {
    // D+1 em diante: o dia 0 fica reservado para o vídeo âncora do YouTube.
    const dayOffset = Math.floor(index / slotsPerDay) % PLAN_HORIZON_DAYS;
    const planDay = dayOffset + 1;
    const hour = PUBLISH_SLOTS_BRT[index % slotsPerDay];
    return {
      ...item,
      planDay,
      scheduledAt: slotToUtcIso(now, planDay, hour),
    };
  });
}

/** Resumo legível do plano, para exibir na UI após a aprovação. */
export function summarizePlan(planned: PlannedItem[]): { day: number; date: string; items: PlannedItem[] }[] {
  const byDay = new Map<number, PlannedItem[]>();
  for (const item of planned) {
    if (!byDay.has(item.planDay)) byDay.set(item.planDay, []);
    byDay.get(item.planDay)!.push(item);
  }
  return [...byDay.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([day, dayItems]) => ({
      day,
      date: dayItems[0]?.scheduledAt ?? '',
      items: dayItems.sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt)),
    }));
}
