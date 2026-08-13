"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { aiDecision, Card, freshDeck, handName, handScore, Player } from "./poker";
import { claimDailyBonus, estDayKey, loadPokerEconomy, savePokerEconomy } from "./bankroll";

const NAMES = ["你", "沈砚", "阿岚", "老周", "白露"];
const SEATS = ["south", "west", "northwest", "northeast", "east"];
const PHASES = ["翻牌前", "翻牌", "转牌", "河牌"];
type LogEntry = { id: number; street: string; player: string; action: string; amount?: number; result?: boolean };

function initialPlayers(): Player[] {
  return NAMES.map((name, id) => ({ id, name, stack: 1000, cards: [], folded: false, allIn: false, bet: 0, lastAction: "等待" }));
}

function CardView({ card, hidden = false, delay = 0, small = false }: { card?: Card; hidden?: boolean; delay?: number; small?: boolean }) {
  const red = card?.suit === "♥" || card?.suit === "♦";
  return (
    <div className={`playing-card ${hidden ? "card-back" : ""} ${red ? "red" : "black"} ${small ? "small" : ""}`} style={{ animationDelay: `${delay}ms` }}>
      {!hidden && card && <><span className="rank">{card.rank}</span><span className="suit">{card.suit}</span><span className="center-suit">{card.suit}</span></>}
      {hidden && <div className="back-mark">♠</div>}
    </div>
  );
}

export default function PokerGame() {
  const [mounted, setMounted] = useState(false);
  const [players, setPlayers] = useState<Player[]>(initialPlayers);
  const [board, setBoard] = useState<Card[]>([]);
  const [pot, setPot] = useState(0);
  const [currentBet, setCurrentBet] = useState(0);
  const [phase, setPhase] = useState(0);
  const [handNo, setHandNo] = useState(0);
  const [dealer, setDealer] = useState(0);
  const [busy, setBusy] = useState(false);
  const [handOver, setHandOver] = useState(true);
  const [reveal, setReveal] = useState(false);
  const [message, setMessage] = useState("入座已备，请开始第一局");
  const [thinking, setThinking] = useState<number | null>(null);
  const [raise, setRaise] = useState(80);
  const [log, setLog] = useState<LogEntry[]>([{ id: 0, street: "准备", player: "牌桌", action: "盲注 10 / 20" }]);
  const [winnerIds, setWinnerIds] = useState<number[]>([]);
  const [resultReason, setResultReason] = useState("");
  const [claimedDay, setClaimedDay] = useState("");
  const [clock, setClock] = useState(() => new Date());
  const [mobileInfoOpen, setMobileInfoOpen] = useState(false);
  const deckRef = useRef<Card[]>([]);
  const playersRef = useRef(players);
  const potRef = useRef(pot);
  const betRef = useRef(currentBet);
  const actedRef = useRef<Set<number>>(new Set());
  const aiRaiseCountRef = useRef(0);
  const runAiRef = useRef<() => void>(() => undefined);
  useEffect(() => { playersRef.current = players; }, [players]);
  useEffect(() => { potRef.current = pot; }, [pot]);
  useEffect(() => { betRef.current = currentBet; }, [currentBet]);
  useEffect(() => {
    const hydrate = window.setTimeout(() => {
      const economy = loadPokerEconomy();
      setClaimedDay(economy.claimedDay);
      setPlayers((old) => {
        const next = old.map((player) => player.id === 0 ? { ...player, stack: economy.chips } : player);
        playersRef.current = next;
        return next;
      });
      setMounted(true);
    }, 0);
    const timer = window.setInterval(() => setClock(new Date()), 30000);
    return () => { window.clearTimeout(hydrate); window.clearInterval(timer); };
  }, []);
  useEffect(() => {
    if (!mounted) return;
    savePokerEconomy({ chips: players[0]?.stack ?? 0, claimedDay });
  }, [mounted, players, claimedDay]);

  const human = players[0];
  const toCall = Math.max(0, currentBet - human.bet);
  const maxRaise = Math.max(Math.min(human.stack, toCall + 40), human.stack);
  const minRaise = Math.min(human.stack, Math.max(toCall + 40, currentBet + 20));
  const shownRaise = Math.min(maxRaise, Math.max(minRaise, raise));
  const todayEst = estDayKey(clock);
  const canClaimDaily = claimedDay !== todayEst;
  const setRaisePreset = (value: number) => setRaise(Math.min(maxRaise, Math.max(minRaise, Math.round(value / 10) * 10)));

  function claimBonus() {
    const result = claimDailyBonus({ chips: playersRef.current[0]?.stack ?? 0, claimedDay }, todayEst);
    if (!result.claimed) return;
    const next = playersRef.current.map((player) => player.id === 0 ? { ...player, stack: result.economy.chips, lastAction: "签到 +1,000" } : player);
    playersRef.current = next;
    setPlayers(next);
    setClaimedDay(result.economy.claimedDay);
    setMessage("每日签到成功 · 获得 1,000 筹码");
  }

  const addLog = useCallback((entry: Omit<LogEntry, "id">) => {
    setLog((old) => [{ ...entry, id: Date.now() + old.length }, ...old].slice(0, 14));
  }, []);

  const pay = useCallback((id: number, amount: number, action: string) => {
    const current = playersRef.current.find((p) => p.id === id);
    if (!current) return 0;
    const paid = Math.min(current.stack, Math.max(0, amount));
    const next = playersRef.current.map((p) => p.id === id ? { ...p, stack: p.stack - paid, bet: p.bet + paid, allIn: p.stack === paid, lastAction: action } : p);
    playersRef.current = next;
    setPlayers(next);
    potRef.current += paid;
    setPot(potRef.current);
    return paid;
  }, []);

  const foldPlayer = useCallback((id: number) => {
    const next = playersRef.current.map((p) => p.id === id ? { ...p, folded: true, lastAction: "弃牌" } : p);
    playersRef.current = next;
    setPlayers(next);
    actedRef.current.add(id);
  }, []);

  const award = useCallback((winners: Player[], reason: string) => {
    const share = Math.floor(potRef.current / winners.length);
    const winnerIds = new Set(winners.map((w) => w.id));
    setPlayers((old) => old.map((p) => winnerIds.has(p.id) ? { ...p, stack: p.stack + share, lastAction: "赢得底池" } : p));
    setMessage(`${winners.map((w) => w.name).join("、")}赢得 ${potRef.current} 筹码 · ${reason}`);
    setWinnerIds([...winnerIds]);
    setResultReason(reason);
    addLog({ street: "结算", player: winners.map((w) => w.name).join("、"), action: "赢得底池", amount: potRef.current, result: true });
    setReveal(true); setHandOver(true); setBusy(false); setThinking(null);
  }, [addLog]);

  const settle = useCallback(() => {
    const live = playersRef.current.filter((p) => !p.folded);
    if (live.length === 1) { award(live, "其余玩家均已弃牌"); return; }
    const scored = live.map((p) => ({ p, score: handScore([...p.cards, ...board]) }));
    scored.sort((a, b) => {
      for (let i = 0; i < Math.max(a.score.length, b.score.length); i++) if ((a.score[i] ?? 0) !== (b.score[i] ?? 0)) return (b.score[i] ?? 0) - (a.score[i] ?? 0);
      return 0;
    });
    const top = scored[0].score.join(",");
    award(scored.filter((x) => x.score.join(",") === top).map((x) => x.p), handName(scored[0].score));
  }, [award, board]);

  const nextStreet = useCallback(() => {
    const live = playersRef.current.filter((p) => !p.folded);
    if (live.length === 1) { award(live, "其余玩家均已弃牌"); return; }
    const resetPlayers = playersRef.current.map((p) => ({ ...p, bet: 0, lastAction: p.folded ? "已弃牌" : "等待" }));
    playersRef.current = resetPlayers;
    setPlayers(resetPlayers);
    actedRef.current = new Set();
    aiRaiseCountRef.current = 0;
    setCurrentBet(0); betRef.current = 0;
    if (phase === 0) setBoard(deckRef.current.splice(0, 3));
    else if (phase < 3) setBoard((old) => [...old, deckRef.current.shift()!]);
    else { setReveal(true); setTimeout(settle, 700); return; }
    setPhase((v) => v + 1);
    const humanCanAct = !resetPlayers[0].folded && !resetPlayers[0].allIn;
    setMessage(humanCanAct ? `${PHASES[phase + 1]} · 轮到你行动` : `${PHASES[phase + 1]} · AI 继续对局`);
    setBusy(!humanCanAct);
    if (!humanCanAct) setTimeout(() => runAiRef.current(), 320);
  }, [award, phase, settle]);

  const runAi = useCallback(async () => {
    setBusy(true);
    for (const id of [1, 2, 3, 4]) {
      const p = playersRef.current[id];
      if (!p || p.folded || p.allIn || p.stack <= 0) continue;
      if (actedRef.current.has(id) && p.bet >= betRef.current) continue;
      setThinking(id); setMessage(`${p.name}正在研判牌局…`);
      await new Promise((r) => setTimeout(r, 750 + Math.random() * 650));
      const call = Math.max(0, betRef.current - p.bet);
      const liveOpponents = playersRef.current.filter((candidate) => candidate.id !== id && !candidate.folded).length;
      const position = ((id - dealer + 5) % 5) / 4;
      const bigBlindId = (dealer + 2) % 5;
      const smallBlindId = (dealer + 1) % 5;
      const callers = playersRef.current.filter((candidate) => candidate.id !== id && !candidate.folded && actedRef.current.has(candidate.id) && candidate.bet >= betRef.current).length;
      const playersBehind = playersRef.current.slice(id + 1).filter((candidate) => !candidate.folded && !candidate.allIn).length;
      const d = aiDecision(p.cards, board, call, potRef.current, p.stack, {
        canRaise: aiRaiseCountRef.current === 0,
        opponents: liveOpponents,
        position,
        bigBlind: 20,
        betTo: betRef.current,
        callers,
        playersBehind,
        isBigBlind: id === bigBlindId,
        isSmallBlind: id === smallBlindId,
        streetRaises: aiRaiseCountRef.current + Number(betRef.current > (phase === 0 ? 20 : 0)),
      });
      if (d.type === "fold") {
        foldPlayer(id);
        addLog({ street: PHASES[phase], player: p.name, action: "弃牌" });
      } else if (d.type === "raise") {
        const paid = pay(id, d.amount, `加注至 ${p.bet + d.amount}`);
        const newBet = p.bet + paid; setCurrentBet(newBet); betRef.current = newBet;
        aiRaiseCountRef.current += 1;
        actedRef.current = new Set([id]);
        addLog({ street: PHASES[phase], player: p.name, action: "加注至", amount: newBet });
      } else {
        pay(id, d.amount, d.type === "call" ? `跟注 ${d.amount}` : "过牌");
        actedRef.current.add(id);
        addLog({ street: PHASES[phase], player: p.name, action: d.type === "call" ? "跟注" : "过牌", amount: d.type === "call" ? d.amount : undefined });
      }
      await new Promise((r) => setTimeout(r, 280));
      if (playersRef.current.filter((x) => !x.folded).length === 1) break;
    }
    setThinking(null);
    const live = playersRef.current.filter((p) => !p.folded);
    if (live.length === 1) { award(live, "其余玩家均已弃牌"); return; }
    const currentHuman = playersRef.current[0];
    const humanMustRespond = !currentHuman.folded && !currentHuman.allIn && (!actedRef.current.has(0) || currentHuman.bet < betRef.current);
    if (humanMustRespond) {
      setBusy(false);
      setMessage(currentHuman.bet < betRef.current ? `有人加注至 ${betRef.current} · 请跟注、再加注或弃牌` : `${PHASES[phase]} · 轮到你行动`);
      return;
    }
    const unsettledAi = playersRef.current.slice(1).some((p) => !p.folded && !p.allIn && (!actedRef.current.has(p.id) || p.bet < betRef.current));
    if (unsettledAi) { setTimeout(() => runAiRef.current(), 250); return; }
    nextStreet();
  }, [addLog, award, board, dealer, foldPlayer, nextStreet, pay, phase]);
  useEffect(() => { runAiRef.current = () => { void runAi(); }; }, [runAi]);

  function startHand() {
    if (playersRef.current[0]?.stack <= 0) {
      setMessage(canClaimDaily ? "筹码已经输光，请先领取每日签到" : "筹码已经输光，下一次美东时间 00:00 可签到");
      return;
    }
    const deck = freshDeck(); deckRef.current = deck;
    const nextDealer = (dealer + 1) % 5; setDealer(nextDealer);
    const reset = players.map((p) => ({ ...p, stack: p.id === 0 ? p.stack : (p.stack || 1000), cards: [deck.shift()!, deck.shift()!], folded: false, allIn: false, bet: 0, lastAction: "已入局" }));
    setPlayers(reset); playersRef.current = reset;
    setBoard([]); setPot(0); potRef.current = 0; setCurrentBet(0); betRef.current = 0; setPhase(0);
    setHandNo((v) => v + 1); setReveal(false); setHandOver(false); setBusy(false); setThinking(null); setWinnerIds([]); setResultReason(""); actedRef.current = new Set(); aiRaiseCountRef.current = 0;
    const sb = (nextDealer + 1) % 5, bb = (nextDealer + 2) % 5;
    setLog([
      { id: Date.now(), street: "翻牌前", player: reset[bb].name, action: "大盲", amount: 20 },
      { id: Date.now() + 1, street: "翻牌前", player: reset[sb].name, action: "小盲", amount: 10 },
      { id: Date.now() + 2, street: `第 ${handNo + 1} 局`, player: "牌桌", action: "洗牌并发牌" },
    ]);
    setTimeout(() => { pay(sb, 10, "小盲 10"); pay(bb, 20, "大盲 20"); setCurrentBet(20); betRef.current = 20; setMessage("翻牌前 · 轮到你行动"); }, 350);
  }

  function humanAction(type: "fold" | "call" | "raise") {
    if (busy || handOver) return;
    if (type === "fold") {
      foldPlayer(0);
      addLog({ street: PHASES[phase], player: "你", action: "弃牌" }); setTimeout(runAi, 300); return;
    }
    if (type === "call") {
      pay(0, toCall, toCall ? `跟注 ${toCall}` : "过牌"); addLog({ street: PHASES[phase], player: "你", action: toCall ? "跟注" : "过牌", amount: toCall || undefined });
      actedRef.current.add(0);
    } else {
      const amount = Math.min(human.stack, shownRaise);
      pay(0, amount, `加注至 ${human.bet + amount}`); const newBet = human.bet + amount;
      setCurrentBet(newBet); betRef.current = newBet; actedRef.current = new Set([0]); addLog({ street: PHASES[phase], player: "你", action: "加注至", amount: newBet });
    }
    setTimeout(runAi, 350);
  }

  const winRate = useMemo(() => {
    if (!human.cards.length) return 0;
    const s = board.length ? handScore([...human.cards, ...board]) : [];
    const rankValue: Record<string, number> = { "2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,J:11,Q:12,K:13,A:14 };
    return board.length ? Math.min(96, 18 + s[0] * 10 + (s[1] ?? 5)) : 20 + Math.round((rankValue[human.cards[0].rank] + rankValue[human.cards[1].rank]) / 3);
  }, [human.cards, board]);

  const showdownHands = useMemo(() => {
    const hands = new Map<number, string>();
    if (reveal && board.length === 5) players.filter((p) => !p.folded).forEach((p) => hands.set(p.id, handName(handScore([...p.cards, ...board]))));
    return hands;
  }, [board, players, reveal]);

  if (!mounted) {
    return <main className="poker-loading" aria-label="正在布置牌桌"><span>♠</span><strong>正在布置牌桌</strong></main>;
  }

  return (
    <main className="game-shell">
      <header className="topbar">
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
        <a className="lobby-link" href="/" aria-label="返回游戏大厅">← <span>游戏大厅</span></a>
        <div className="brand"><div><h1>德州扑克</h1></div></div>
        <div className="table-meta"><span>第 {Math.max(1, handNo)} 局</span><i /><span>盲注 10 / 20</span><i /><span>随机牌组</span></div>
        <button className={`daily-bonus ${canClaimDaily ? "available" : "claimed"}`} onClick={claimBonus} disabled={!canClaimDaily} aria-label={canClaimDaily ? "领取每日签到一千筹码" : "今日签到已领取"}><span>{canClaimDaily ? "每日签到" : "今日已签"}</span><b>{canClaimDaily ? "+1,000" : "✓"}</b><small>美东 00:00 刷新</small></button>
        <button className="sound-button" aria-label="声音">♪</button>
      </header>

      <section className="game-layout">
        <div className="table-wrap">
          <div className="ambient-light" />
          <div className="poker-table">
            <div className="table-inlay" />
            <div className="deck-stack"><span>♠</span></div>
            <div className="pot-display"><small>底池</small><strong>{pot}</strong><div className="chip-row"><b /><b /><b /><b /></div></div>
            <div className="community-cards">
              {[0,1,2,3,4].map((i) => board[i] ? <CardView key={`${board[i].rank}${board[i].suit}`} card={board[i]} delay={i * 120} small /> : <div className="card-slot" key={i} />)}
            </div>
            <div className="street-label">{handOver ? "本局结算" : PHASES[phase]}</div>
            {handOver && winnerIds.length > 0 && <div className="showdown-result">
              <small>本局胜者</small>
              <strong>{players.filter((p) => winnerIds.includes(p.id)).map((p) => p.name).join("、")}</strong>
              <span>{resultReason} · 赢得 {pot} 筹码</span>
            </div>}

            {players.map((p, index) => (
              <div className={`seat seat-${SEATS[index]} ${p.folded ? "folded" : ""} ${thinking === p.id ? "thinking" : ""} ${winnerIds.includes(p.id) ? "winner" : ""} ${reveal && !p.folded && !winnerIds.includes(p.id) ? "showdown-loser" : ""}`} key={p.id}>
                {p.id !== 0 && <div className="hole-cards">
                  {p.cards.map((c, i) => <CardView key={i} card={c} hidden={!reveal && !handOver} delay={100 + i * 90} small />)}
                </div>}
                {p.id === 0 && <div className="hole-cards human-cards">{p.cards.map((c, i) => <CardView key={i} card={c} delay={100 + i * 90} />)}</div>}
                {showdownHands.has(p.id) && <div className={`hand-badge ${winnerIds.includes(p.id) ? "best" : ""}`}>{winnerIds.includes(p.id) ? "胜出 · " : ""}{showdownHands.get(p.id)}</div>}
                <div className="player-plaque">
                  <div className="avatar">{p.name.slice(0,1)}{dealer === p.id && <em>D</em>}</div>
                  <div className="player-copy"><div><strong>{p.name}</strong></div><b>{p.stack.toLocaleString()} <small>筹码</small></b></div>
                </div>
                <div className={`action-bubble ${thinking === p.id ? "active" : ""}`}><span className="action-content" key={`${p.id}-${thinking === p.id ? "thinking" : p.lastAction}`}>{thinking === p.id ? <><span className="dots">•••</span> 思考中</> : p.lastAction}</span></div>
              </div>
            ))}
          </div>
          <div className="status-ribbon"><span className="status-gem" />{message}</div>
        </div>

        <aside className="side-panel">
          <div className="panel-heading"><div><h2>对局信息</h2><p>对手行动与当前局势</p></div></div>
          <div className="odds-card"><div><span>当前牌力参考</span><strong>{winRate}%</strong></div><div className="meter"><i style={{ width: `${winRate}%` }} /></div><small>根据已知牌面估算，仅供牌桌决策参考</small></div>
          <div className="personality-list opponent-list">
            {players.slice(1).map((p) => <div className={`personality ${thinking === p.id ? "active" : ""}`} key={p.id}><span className="mini-avatar">{p.name[0]}</span><div><strong>{p.name}</strong><small>{p.folded ? "本局已弃牌" : `${p.stack.toLocaleString()} 筹码`}</small></div><b>{p.lastAction}</b></div>)}
          </div>
          {reveal && showdownHands.size > 0 && <div className="showdown-panel"><h3>开牌结果</h3>{players.filter((p) => showdownHands.has(p.id)).sort((a, b) => Number(winnerIds.includes(b.id)) - Number(winnerIds.includes(a.id))).map((p) => <div className={winnerIds.includes(p.id) ? "best" : ""} key={p.id}><strong>{p.name}</strong><span>{p.cards.map((c) => `${c.rank}${c.suit}`).join(" ")}</span><b>{showdownHands.get(p.id)}</b></div>)}</div>}
          <div className="action-log"><div className="log-heading"><h3>下注历史</h3><span>最新在上</span></div><div className="log-columns"><span>阶段</span><span>玩家</span><span>动作</span><span>筹码</span></div><div className="log-rows">{log.map((entry) => <div className={`log-row ${entry.result ? "result" : ""}`} key={entry.id}><span>{entry.street}</span><strong>{entry.player}</strong><b>{entry.action}</b><em>{entry.amount === undefined ? "—" : entry.amount}</em></div>)}</div></div>
        </aside>
      </section>

      <button className="mobile-info-toggle" type="button" aria-expanded={mobileInfoOpen} onClick={() => setMobileInfoOpen((open) => !open)}><span>牌局信息</span><b>{winRate}%</b></button>
      <aside className={`mobile-info-drawer ${mobileInfoOpen ? "open" : ""}`} aria-hidden={!mobileInfoOpen}>
        <header><strong>牌局信息</strong><button type="button" onClick={() => setMobileInfoOpen(false)} aria-label="关闭牌局信息">×</button></header>
        <div className="mobile-strength"><span>当前牌力参考</span><strong>{winRate}%</strong><div className="meter"><i style={{ width: `${winRate}%` }} /></div></div>
        <div className="mobile-opponents">{players.slice(1).map((p) => <div key={p.id}><strong>{p.name}</strong><span>{p.folded ? "已弃牌" : p.lastAction}</span><b>{p.stack.toLocaleString()}</b></div>)}</div>
        <div className="mobile-log">{log.slice(0, 5).map((entry) => <p key={entry.id}><span>{entry.street}</span><strong>{entry.player}</strong><b>{entry.action}{entry.amount === undefined ? "" : ` ${entry.amount}`}</b></p>)}</div>
      </aside>

      <footer className="action-dock">
        {handOver ? human.stack <= 0 ? <div className="bankrupt-notice"><div><strong>筹码已经输光</strong><span>{canClaimDaily ? "领取今日签到即可继续" : "请在美东时间 00:00 后回来签到"}</span></div><button onClick={claimBonus} disabled={!canClaimDaily}>{canClaimDaily ? "签到领取 1,000" : "今日已领取"}</button></div> : <button className="deal-button" onClick={startHand}><span>开始新一局</span><small>当前筹码 {human.stack.toLocaleString()} · 自动保存</small></button> : human.folded ? <div className="spectating-notice"><strong>你已弃牌</strong><span>AI 正在完成本局</span></div> : <>
          <button className="action ghost" disabled={busy} onClick={() => humanAction("fold")}><span>弃牌</span><small>Fold</small></button>
          <button className="action pale" disabled={busy} onClick={() => humanAction("call")}><span>{toCall ? `跟注 ${toCall}` : "过牌"}</span><small>{toCall ? "Call" : "Check"}</small></button>
          <div className="raise-control"><div className="raise-head"><span>加注筹码</span><strong>{shownRaise}</strong></div><div className="raise-row"><button type="button" disabled={busy || human.stack <= toCall} onClick={() => setRaisePreset(shownRaise - 10)} aria-label="加注减少十">−</button><input aria-label="加注筹码" type="range" min={minRaise} max={Math.max(minRaise, maxRaise)} step="10" value={shownRaise} disabled={busy || human.stack <= toCall} onChange={(e) => setRaise(Number(e.target.value))} /><button type="button" disabled={busy || human.stack <= toCall} onClick={() => setRaisePreset(shownRaise + 10)} aria-label="加注增加十">＋</button></div><div className="raise-presets"><button type="button" onClick={() => setRaisePreset(toCall + pot * .5)}>半池</button><button type="button" onClick={() => setRaisePreset(toCall + pot)}>一池</button><button type="button" onClick={() => setRaisePreset(human.stack)}>全下</button></div></div>
          <button className="action gold" disabled={busy || human.stack <= toCall} onClick={() => humanAction("raise")}><span>加注</span><small>Raise</small></button>
        </>}
      </footer>
    </main>
  );
}
