import React from 'react';
import { Clock, RefreshCw, ShieldCheck, Zap, Terminal } from 'lucide-react';
import { TestClock, GlobalLedgerVerification } from '../types';

interface HeaderProps {
  clock: TestClock | null;
  verification: GlobalLedgerVerification | null;
  onReset: () => void;
  isResetting: boolean;
  isAdvancing: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  clock,
  verification,
  onReset,
  isResetting,
  isAdvancing,
}) => {
  const formatVirtualDate = (isoString?: string) => {
    if (!isoString) return 'Loading virtual time...';
    const date = new Date(isoString);
    return date.toUTCString().replace('GMT', 'UTC');
  };

  return (
    <header className="border-b border-surface-border bg-surface-card/90 backdrop-blur-md sticky top-0 z-50 px-6 py-3.5">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        
        {/* Brand & Invariant Proof */}
        <div className="flex items-center gap-3.5">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-stripe-600 to-indigo-400 p-0.5 shadow-lg shadow-stripe-500/20 flex items-center justify-center">
            <Clock className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                CHRONOS
                <span className="text-[10px] font-mono tracking-widest uppercase bg-stripe-500/20 text-stripe-300 px-2 py-0.5 rounded-full border border-stripe-500/30">
                  Stripe-Grade Engine
                </span>
              </h1>
            </div>
            <p className="text-xs text-slate-400">
              Immutable Double-Entry Ledger &amp; Virtual Test Clock Simulator
            </p>
          </div>
        </div>

        {/* Global Balance Proof Pill */}
        {verification && (
          <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>
              SUM(DEBIT) - SUM(CREDIT) = <strong className="text-emerald-300">$0.00</strong>
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        )}

        {/* Virtual Clock Display & Reset Controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-surface-base px-3.5 py-1.5 rounded-lg border border-surface-border text-xs font-mono">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isAdvancing ? 'bg-amber-400' : 'bg-emerald-400'}`} />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isAdvancing ? 'bg-amber-500' : 'bg-emerald-500'}`} />
            </span>
            <span className="text-slate-400">VIRTUAL TIME:</span>
            <span className="text-white font-semibold tracking-wide">
              {formatVirtualDate(clock?.current_virtual_time)}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded uppercase font-semibold ${
              isAdvancing ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-slate-800 text-slate-300'
            }`}>
              {isAdvancing ? 'Advancing' : clock?.status || 'READY'}
            </span>
          </div>

          <button
            onClick={onReset}
            disabled={isResetting}
            title="Wipe and re-seed database back to canonical initial state"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-surface-subtle text-slate-300 hover:text-white border border-surface-border text-xs font-medium transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isResetting ? 'animate-spin' : ''}`} />
            <span>Reset DB</span>
          </button>
        </div>

      </div>
    </header>
  );
};
