import test from 'node:test';
import assert from 'node:assert/strict';
import { claimDailyBonus, estDayKey, loadPokerEconomy } from '../app/bankroll.ts';

test('EST day key follows New York calendar day', () => {
  assert.equal(estDayKey(new Date('2026-01-02T04:30:00Z')), '2026-01-01');
  assert.equal(estDayKey(new Date('2026-01-02T05:30:00Z')), '2026-01-02');
});

test('daily 1000 chip bonus can only be claimed once per EST day', () => {
  const first = claimDailyBonus({ chips:0, claimedDay:'' }, '2026-08-11');
  assert.equal(first.claimed, true);
  assert.equal(first.economy.chips, 1000);
  const second = claimDailyBonus(first.economy, '2026-08-11');
  assert.equal(second.claimed, false);
  assert.equal(second.economy.chips, 1000);
});

test('a returning player keeps a zero bankroll instead of being reset', () => {
  const storage = { getItem: () => JSON.stringify({ chips:0, claimedDay:'2026-08-11' }) };
  assert.equal(loadPokerEconomy(storage).chips, 0);
});
