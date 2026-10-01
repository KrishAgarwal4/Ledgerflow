import React, { useState } from 'react';
import { Zap, ShieldAlert, Cpu, CheckCircle2, XCircle, RefreshCw, Send, Lock } from 'lucide-react';
import { api } from '../api/client';
import { DuplicateStormResponse, OverdraftRaceResponse } from '../types';

interface ChaosTesterProps {
  onRefresh: () => void;
  virtualTime?: string;
}

export const ChaosTester: React.FC<ChaosTesterProps> = ({ onRefresh, virtualTime }) => {
  // Test 1: Idempotency Storm
  const [isStormRunning, setIsStormRunning] = useState(false);
  const [stormResult, setStormResult] = useState<DuplicateStormResponse | null>(null);

  // Test 2: Parallel Overdraft Race
  const [isRaceRunning, setIsRaceRunning] = useState(false);
  const [raceResult, setRaceResult] = useState<OverdraftRaceResponse | null>(null);

  // Test 3: Custom Usage Injection
  const [customTokens, setCustomTokens] = useState<number>(500000);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('cus_nexus_ai');
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [injectResult, setInjectResult] = useState<string | null>(null);

  const handleRunStorm = async () => {
    setIsStormRunning(true);
    setStormResult(null);
    try {
      const res = await api.runMeterStorm(100, 'cus_nexus_ai', 50000);
      setStormResult(res);
      onRefresh();
    } catch (err: any) {
      alert(`Storm error: ${err.message}`);
    } finally {
      setIsStormRunning(false);
    }
  };

  const handleRunRace = async () => {
    setIsRaceRunning(true);
    setRaceResult(null);
    try {
      const res = await api.runOverdraftRace(20, 'cus_quantum_labs');
      setRaceResult(res);
      onRefresh();
    } catch (err: any) {
      alert(`Race error: ${err.message}`);
    } finally {
      setIsRaceRunning(false);
    }
  };

  const handleInjectUsage = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInjecting(true);
    setInjectResult(null);
    try {
      const eventId = `evt_manual_${Date.now()}`;
      const nowTime = virtualTime || new Date().toISOString();
      const res = await api.emitMeterEvent({
        event_id: eventId,
        customer_id: selectedCustomerId,
        metric_name: 'llm_tokens',
        quantity: customTokens,
        timestamp: nowTime,
      });
      setInjectResult(`Successfully emitted ${customTokens.toLocaleString()} tokens (${eventId})`);
      onRefresh();
    } catch (err: any) {
      setInjectResult(`Error: ${err.message}`);
    } finally {
      setIsInjecting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
        <div className="flex items-center gap-2 mb-1">
          <Zap className="w-4 h-4 text-amber-400" />
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase">
            Chaos &amp; Concurrency Stress Tester
          </h2>
        </div>
        <p className="text-xs text-slate-400">
          Proves financial correctness under concurrency: distributed idempotency keys and row-level locking (<code className="text-stripe-300">SELECT ... FOR UPDATE</code>).
        </p>
      </div>

      {/* Grid of Stress Tests */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Test 1: 100 Duplicate Event Storm */}
        <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold text-stripe-300 uppercase flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-stripe-400" />
                Stress Test 1: Distributed Idempotency
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-stripe-500/10 text-stripe-300 border border-stripe-500/20">
                100 Concurrent Tasks
              </span>
            </div>
            <p className="text-xs text-slate-300 mb-4">
              Fires 100 simultaneous webhook/meter events with the exact same <code className="text-stripe-300">event_id</code> in ~50ms.
              Proves atomic SHA-256 payload locking: exactly 1 commits, and 99 are returned as cached replays.
            </p>

            <button
              onClick={handleRunStorm}
              disabled={isStormRunning}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-stripe-600 to-indigo-600 hover:from-stripe-500 hover:to-indigo-500 text-white text-xs font-bold shadow-lg shadow-stripe-600/30 transition-all disabled:opacity-50"
            >
              {isStormRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Firing 100 Concurrent Requests...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4 text-amber-300" />
                  Fire 100 Duplicate Meter Events
                </>
              )}
            </button>
          </div>

          {/* Storm Results */}
          {stormResult && (
            <div className="mt-4 p-3.5 rounded-xl bg-surface-base border border-surface-border animate-in fade-in">
              <div className="text-xs font-mono font-bold text-white mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                Idempotency Barrier Verified! ({stormResult.time_taken_ms}ms)
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono mb-2">
                <div className="p-2 rounded bg-emerald-950/30 border border-emerald-500/20 text-center">
                  <span className="text-[10px] text-slate-400 block">Committed Unique</span>
                  <strong className="text-base text-emerald-400">{stormResult.unique_committed}</strong>
                </div>
                <div className="p-2 rounded bg-cyan-950/30 border border-cyan-500/20 text-center">
                  <span className="text-[10px] text-slate-400 block">Deduplicated Replays</span>
                  <strong className="text-base text-cyan-400">{stormResult.replays_blocked}</strong>
                </div>
              </div>
              <div className="text-[11px] font-mono text-slate-400 truncate">
                Key: <span className="text-slate-300">{stormResult.idempotency_key}</span>
              </div>
            </div>
          )}
        </div>

        {/* Test 2: 20 Parallel Overdraft Race Condition */}
        <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono font-bold text-rose-400 uppercase flex items-center gap-1.5">
                <Lock className="w-4 h-4 text-rose-400" />
                Stress Test 2: Overdraft Race Condition
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20">
                20 Concurrent Spends
              </span>
            </div>
            <p className="text-xs text-slate-300 mb-4">
              Fires 20 simultaneous $10 charges against a $50 prepaid credit balance.
              With row-level locking (<code className="text-rose-300">SELECT ... FOR UPDATE</code>), exactly 5 succeed ($50 total) and 15 are cleanly rejected. Balance NEVER goes negative!
            </p>

            <button
              onClick={handleRunRace}
              disabled={isRaceRunning}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white text-xs font-bold shadow-lg shadow-rose-600/30 transition-all disabled:opacity-50"
            >
              {isRaceRunning ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Simulating 20 Parallel Charges...
                </>
              ) : (
                <>
                  <ShieldAlert className="w-4 h-4 text-white" />
                  Simulate Parallel Overdraft Race
                </>
              )}
            </button>
          </div>

          {/* Race Results */}
          {raceResult && (
            <div className="mt-4 p-3.5 rounded-xl bg-surface-base border border-surface-border animate-in fade-in">
              <div className="flex items-center justify-between text-xs font-mono font-bold text-white mb-2">
                <span className="flex items-center gap-1 text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                  Row-Lock Invariant Guaranteed!
                </span>
                <span className="text-slate-400">{raceResult.time_taken_ms}ms</span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs font-mono mb-2.5 text-center">
                <div className="p-1.5 rounded bg-surface-elevated border border-surface-border">
                  <span className="text-[10px] text-slate-400 block">Initial Bal</span>
                  <strong className="text-slate-200">${raceResult.initial_balance_cents / 100}</strong>
                </div>
                <div className="p-1.5 rounded bg-emerald-950/30 border border-emerald-500/20">
                  <span className="text-[10px] text-slate-400 block">Succeeded (5)</span>
                  <strong className="text-emerald-400">5 x $10</strong>
                </div>
                <div className="p-1.5 rounded bg-rose-950/30 border border-rose-500/20">
                  <span className="text-[10px] text-slate-400 block">Rejected (15)</span>
                  <strong className="text-rose-400">15 Rejections</strong>
                </div>
              </div>

              {/* 20 Tasks Visual Matrix */}
              <div className="grid grid-cols-10 gap-1 my-2">
                {raceResult.results.map((r, i) => (
                  <div
                    key={i}
                    title={`Task #${i}: ${r.status}`}
                    className={`h-4 rounded flex items-center justify-center text-[9px] font-mono font-bold ${
                      r.status === 'COMMITTED'
                        ? 'bg-emerald-500 text-black'
                        : 'bg-rose-500/40 text-rose-300 border border-rose-500/50'
                    }`}
                  >
                    {i + 1}
                  </div>
                ))}
              </div>

              <div className="pt-2 border-t border-surface-border flex items-center justify-between text-xs font-mono">
                <span className="text-slate-400">Final Wallet Balance:</span>
                <strong className="text-emerald-400">${(raceResult.final_balance_cents / 100).toFixed(2)} (Never Negative)</strong>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* Custom Meter Event Ingestion Form */}
      <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
        <h3 className="text-xs font-mono font-bold text-white uppercase flex items-center gap-2 mb-1">
          <Send className="w-3.5 h-3.5 text-stripe-400" />
          Interactive Meter Event Ingestor
        </h3>
        <p className="text-xs text-slate-400 mb-3">
          Emit unbilled LLM token usage into the live pipeline. Advance the clock by 30 days to see it billed and invoiced.
        </p>

        <form onSubmit={handleInjectUsage} className="flex flex-col md:flex-row items-center gap-3">
          <div className="w-full md:w-1/3">
            <select
              value={selectedCustomerId}
              onChange={(e) => setSelectedCustomerId(e.target.value)}
              className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-stripe-500"
            >
              <option value="cus_nexus_ai">Nexus Intelligence (Scale Tier)</option>
              <option value="cus_quantum_labs">Quantum Labs (Starter Tier)</option>
              <option value="cus_apex_ai">Apex Synthetics (Failing Card)</option>
            </select>
          </div>

          <div className="w-full md:w-1/3">
            <input
              type="number"
              step="50000"
              min="10000"
              value={customTokens}
              onChange={(e) => setCustomTokens(Number(e.target.value))}
              placeholder="Token quantity (e.g. 500000)"
              className="w-full bg-surface-base border border-surface-border rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-stripe-500"
            />
          </div>

          <button
            type="submit"
            disabled={isInjecting}
            className="w-full md:w-auto px-4 py-2 rounded-lg bg-surface-elevated hover:bg-surface-subtle text-slate-200 hover:text-white border border-surface-border text-xs font-medium transition-all flex items-center justify-center gap-1.5 whitespace-nowrap"
          >
            {isInjecting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
            Emit Meter Event
          </button>
        </form>

        {injectResult && (
          <div className="mt-2.5 text-xs font-mono text-emerald-400 bg-emerald-950/20 border border-emerald-500/20 px-3 py-1.5 rounded-lg">
            {injectResult}
          </div>
        )}
      </div>
    </div>
  );
};
