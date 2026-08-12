export const POKER_ECONOMY_KEY = 'tzt-poker-economy-v1';

export type PokerEconomy = { chips: number; claimedDay: string };

export function estDayKey(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function normalizePokerEconomy(value: unknown): PokerEconomy {
  const source = value && typeof value === 'object' ? value as Partial<PokerEconomy> : {};
  return {
    chips: Math.max(0, Math.floor(Number(source.chips) || 0)),
    claimedDay: typeof source.claimedDay === 'string' ? source.claimedDay : '',
  };
}

export function loadPokerEconomy(storage: Storage = globalThis.localStorage): PokerEconomy {
  try {
    const raw = storage?.getItem(POKER_ECONOMY_KEY);
    return raw ? normalizePokerEconomy(JSON.parse(raw)) : { chips: 1000, claimedDay: '' };
  } catch { return { chips: 1000, claimedDay: '' }; }
}

export function savePokerEconomy(economy: PokerEconomy, storage: Storage = globalThis.localStorage) {
  const normalized = normalizePokerEconomy(economy);
  storage?.setItem(POKER_ECONOMY_KEY, JSON.stringify(normalized));
  return normalized;
}

export function claimDailyBonus(economy: PokerEconomy, dayKey: string, bonus = 1000) {
  const current = normalizePokerEconomy(economy);
  if (current.claimedDay === dayKey) return { economy: current, claimed: false };
  return { economy: { chips: current.chips + bonus, claimedDay: dayKey }, claimed: true };
}
