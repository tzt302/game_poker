"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { aiDecision, Card, freshDeck, handName, handScore, PERSONALITIES, Player, Style } from "./poker";

const NAMES = ["你", "沈砚", "阿岚", "老周", "白露"];
const STYLES: Array<"human" | Style> = ["human", "tight", "aggressive", "balanced", "loose"];
const SEATS = ["south", "west", "northwest", "northeast", "east"];
const PHASES = ["翻牌前", "翻牌", "转牌", "河牌"];

function initialPlayers(): Player[] {
  return NAMES.map((name, id) => ({ id, name, stack: 1000, cards: [], folded: false, allIn: false, bet: 0, lastAction: "等待", style: STYLES[id] }));
}

function CardView({ card, hidden = false, delay = 0, small = false }: { card?: Card; hidden?: boolean; delay?: number; small?: boolean }) {
  const red = card?.suit === "♥" || card?.suit === "♦";
  return (
    <div className={`playing-card ${hidden ? "card-back" : ""} ${red ? "red" : "black"} ${small ? "small" : ""}`} style={{ animationDelay: `${delay}ms` }}>
      {!hidden && card && <><span className="rank">{card.rank}</span><span className="suit">{card.suit}</span><span className="center-suit">{card.suit}</span></>}
      {hidden && <div className="back-mark">金</div>}
    </div>
  );
}

export default function PokerGame() {
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
  const [log, setLog] = useState<string[]>(["牌桌已就绪 · 盲注 10 / 20"]);
  const deckRef = useRef<Card[]>([]);
  const playersRef = useRef(players);
  const potRef = useRef(pot);
  const betRef = useRef(currentBet);
  useEffect(() => { playersRef.current = players; }, [players]);
  useEffect(() => { potRef.current = pot; }, [pot]);
  useEffect(() => { betRef.current = currentBet; }, [currentBet]);

  const human = players[0];
  const toCall = Math.max(0, currentBet - human.bet);
  const maxRaise = Math.max(Math.min(human.stack, toCall + 40), human.stack);
  const minRaise = Math.min(human.stack, Math.max(toCall + 40, currentBet + 20));
  const shownRaise = Math.min(maxRaise, Math.max(minRaise, raise));

  const addLog = useCallback((line: string) => setLog((old) => [line, ...old].slice(0, 7)), []);

  const pay = useCallback((id: number, amount: number, action: string) => {
    let paid = 0;
    setPlayers((old) => old.map((p) => {
      if (p.id !== id) return p;
      paid = Math.min(p.stack, amount);
      return { ...p, stack: p.stack - paid, bet: p.bet + paid, allIn: p.stack === paid, lastAction: action };
    }));
    setPot((v) => v + paid);
    return paid;
  }, []);

  const award = useCallback((winners: Player[], reason: string) => {
    const share = Math.floor(potRef.current / winners.length);
    const winnerIds = new Set(winners.map((w) => w.id));
    setPlayers((old) => old.map((p) => winnerIds.has(p.id) ? { ...p, stack: p.stack + share, lastAction: "赢得底池" } : p));
    setMessage(`${winners.map((w) => w.name).join("、")}赢得 ${potRef.current} 筹码 · ${reason}`);
    addLog(`◆ ${winners.map((w) => w.name).join("、")}赢下底池 ${potRef.current}`);
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
    setPlayers((old) => old.map((p) => ({ ...p, bet: 0, lastAction: p.folded ? "已弃牌" : "等待" })));
    setCurrentBet(0); betRef.current = 0;
    if (phase === 0) setBoard(deckRef.current.splice(0, 3));
    else if (phase < 3) setBoard((old) => [...old, deckRef.current.shift()!]);
    else { setReveal(true); setTimeout(settle, 700); return; }
    setPhase((v) => v + 1);
    setMessage(`${PHASES[phase + 1]} · 轮到你行动`);
    setBusy(false);
  }, [award, phase, settle]);

  const runAi = useCallback(async () => {
    setBusy(true);
    for (const id of [1, 2, 3, 4]) {
      const p = playersRef.current[id];
      if (!p || p.folded || p.allIn || p.stack <= 0) continue;
      setThinking(id); setMessage(`${p.name}正在研判牌局…`);
      await new Promise((r) => setTimeout(r, 750 + Math.random() * 650));
      const call = Math.max(0, betRef.current - p.bet);
      const d = aiDecision(p.style as Style, p.cards, board, call, potRef.current, p.stack);
      if (d.type === "fold") {
        setPlayers((old) => old.map((x) => x.id === id ? { ...x, folded: true, lastAction: "弃牌" } : x));
        addLog(`${p.name} · 弃牌`);
      } else if (d.type === "raise") {
        const paid = pay(id, d.amount, `加注至 ${p.bet + d.amount}`);
        const newBet = p.bet + paid; setCurrentBet(newBet); betRef.current = newBet;
        addLog(`${p.name} · 加注至 ${newBet}`);
      } else {
        pay(id, d.amount, d.type === "call" ? `跟注 ${d.amount}` : "过牌");
        addLog(`${p.name} · ${d.type === "call" ? `跟注 ${d.amount}` : "过牌"}`);
      }
      await new Promise((r) => setTimeout(r, 280));
      if (playersRef.current.filter((x) => !x.folded).length === 1) break;
    }
    setThinking(null);
    const live = playersRef.current.filter((p) => !p.folded);
    if (live.length === 1) award(live, "其余玩家均已弃牌"); else nextStreet();
  }, [addLog, award, board, nextStreet, pay]);

  function startHand() {
    const deck = freshDeck(); deckRef.current = deck;
    const nextDealer = (dealer + 1) % 5; setDealer(nextDealer);
    const reset = players.map((p) => ({ ...p, stack: p.stack || 1000, cards: [deck.shift()!, deck.shift()!], folded: false, allIn: false, bet: 0, lastAction: "已入局" }));
    setPlayers(reset); playersRef.current = reset;
    setBoard([]); setPot(0); potRef.current = 0; setCurrentBet(0); betRef.current = 0; setPhase(0);
    setHandNo((v) => v + 1); setReveal(false); setHandOver(false); setBusy(false); setThinking(null);
    const sb = (nextDealer + 1) % 5, bb = (nextDealer + 2) % 5;
    setTimeout(() => { pay(sb, 10, "小盲 10"); pay(bb, 20, "大盲 20"); setCurrentBet(20); betRef.current = 20; setMessage("翻牌前 · 轮到你行动"); addLog(`第 ${handNo + 1} 局开始 · 随机洗牌完成`); }, 350);
  }

  function humanAction(type: "fold" | "call" | "raise") {
    if (busy || handOver) return;
    if (type === "fold") {
      setPlayers((old) => old.map((p) => p.id === 0 ? { ...p, folded: true, lastAction: "弃牌" } : p));
      addLog("你 · 弃牌"); setTimeout(runAi, 300); return;
    }
    if (type === "call") {
      pay(0, toCall, toCall ? `跟注 ${toCall}` : "过牌"); addLog(`你 · ${toCall ? `跟注 ${toCall}` : "过牌"}`);
    } else {
      const amount = Math.min(human.stack, shownRaise);
      pay(0, amount, `加注至 ${human.bet + amount}`); const newBet = human.bet + amount;
      setCurrentBet(newBet); betRef.current = newBet; addLog(`你 · 加注至 ${newBet}`);
    }
    setTimeout(runAi, 350);
  }

  const winRate = useMemo(() => {
    if (!human.cards.length) return 0;
    const s = board.length ? handScore([...human.cards, ...board]) : [];
    const rankValue: Record<string, number> = { "2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,J:11,Q:12,K:13,A:14 };
    return board.length ? Math.min(96, 18 + s[0] * 10 + (s[1] ?? 5)) : 20 + Math.round((rankValue[human.cards[0].rank] + rankValue[human.cards[1].rank]) / 3);
  }, [human.cards, board]);

  return (
    <main className="game-shell">
      <header className="topbar">
        <div className="brand"><span className="seal">金</span><div><h1>金陵牌局</h1><p>德州扑克 · 人机雅局</p></div></div>
        <div className="table-meta"><span>第 {Math.max(1, handNo)} 局</span><i /><span>盲注 10 / 20</span><i /><span>随机牌组</span></div>
        <button className="sound-button" aria-label="声音">♪</button>
      </header>

      <section className="game-layout">
        <div className="table-wrap">
          <div className="ambient-light" />
          <div className="poker-table">
            <div className="table-inlay" />
            <div className="deck-stack"><span>金</span></div>
            <div className="pot-display"><small>底池</small><strong>{pot}</strong><div className="chip-row"><b /><b /><b /><b /></div></div>
            <div className="community-cards">
              {[0,1,2,3,4].map((i) => board[i] ? <CardView key={`${board[i].rank}${board[i].suit}`} card={board[i]} delay={i * 120} small /> : <div className="card-slot" key={i} />)}
            </div>
            <div className="street-label">{handOver ? "本局结算" : PHASES[phase]}</div>

            {players.map((p, index) => (
              <div className={`seat seat-${SEATS[index]} ${p.folded ? "folded" : ""} ${thinking === p.id ? "thinking" : ""}`} key={p.id}>
                {p.id !== 0 && <div className="hole-cards">
                  {p.cards.map((c, i) => <CardView key={i} card={c} hidden={!reveal && !handOver} delay={100 + i * 90} small />)}
                </div>}
                {p.id === 0 && <div className="hole-cards human-cards">{p.cards.map((c, i) => <CardView key={i} card={c} delay={100 + i * 90} />)}</div>}
                <div className="player-plaque">
                  <div className="avatar">{p.name.slice(0,1)}{dealer === p.id && <em>D</em>}</div>
                  <div className="player-copy"><div><strong>{p.name}</strong>{p.style !== "human" && <span style={{ color: PERSONALITIES[p.style].color }}>{PERSONALITIES[p.style].label}</span>}</div><b>{p.stack.toLocaleString()} <small>筹码</small></b></div>
                </div>
                <div className={`action-bubble ${thinking === p.id ? "active" : ""}`}>{thinking === p.id ? <><span className="dots">•••</span> 思考中</> : p.lastAction}</div>
              </div>
            ))}
          </div>
          <div className="status-ribbon"><span className="status-gem" />{message}</div>
        </div>

        <aside className="side-panel">
          <div className="panel-heading"><span>牌</span><div><h2>牌局研判</h2><p>对手行动与局势一目了然</p></div></div>
          <div className="odds-card"><div><span>当前牌力参考</span><strong>{winRate}%</strong></div><div className="meter"><i style={{ width: `${winRate}%` }} /></div><small>根据已知牌面估算，仅供牌桌决策参考</small></div>
          <div className="personality-list">
            {players.slice(1).map((p) => <div className={`personality ${thinking === p.id ? "active" : ""}`} key={p.id}><span className="mini-avatar">{p.name[0]}</span><div><strong>{p.name}<em style={{ color: PERSONALITIES[p.style as Style].color }}>{PERSONALITIES[p.style as Style].label}</em></strong><small>{PERSONALITIES[p.style as Style].motto}</small></div><b>{p.lastAction}</b></div>)}
          </div>
          <div className="action-log"><h3>行动记事</h3>{log.map((line, i) => <p key={`${line}${i}`}><span>{i ? "·" : "◆"}</span>{line}</p>)}</div>
        </aside>
      </section>

      <footer className="action-dock">
        {handOver ? <button className="deal-button" onClick={startHand}><span>开始新一局</span><small>重新洗牌并随机发牌</small></button> : <>
          <button className="action ghost" disabled={busy} onClick={() => humanAction("fold")}><span>弃牌</span><small>Fold</small></button>
          <button className="action pale" disabled={busy} onClick={() => humanAction("call")}><span>{toCall ? `跟注 ${toCall}` : "过牌"}</span><small>{toCall ? "Call" : "Check"}</small></button>
          <div className="raise-control"><div className="raise-head"><span>加注筹码</span><strong>{shownRaise}</strong></div><input aria-label="加注筹码" type="range" min={minRaise} max={Math.max(minRaise, maxRaise)} step="10" value={shownRaise} disabled={busy || human.stack <= toCall} onChange={(e) => setRaise(Number(e.target.value))} /><div className="raise-ticks"><span>{minRaise}</span><span>半池</span><span>全下 {human.stack}</span></div></div>
          <button className="action gold" disabled={busy || human.stack <= toCall} onClick={() => humanAction("raise")}><span>加注</span><small>Raise</small></button>
        </>}
      </footer>
    </main>
  );
}
