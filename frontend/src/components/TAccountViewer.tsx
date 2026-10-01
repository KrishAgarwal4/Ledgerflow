import React from 'react';
import { Account, AccountType } from '../types';
import { Wallet, Landmark, TrendingUp, AlertTriangle, ShieldCheck } from 'lucide-react';

interface TAccountViewerProps {
  accounts: Account[];
  onSelectAccount?: (account: Account) => void;
  selectedAccountId?: string;
}

export const TAccountViewer: React.FC<TAccountViewerProps> = ({
  accounts,
  onSelectAccount,
  selectedAccountId,
}) => {
  const formatMoney = (cents: number) => {
    const isNegative = cents < 0;
    const absDollars = (Math.abs(cents) / 100).toFixed(2);
    return `${isNegative ? '-' : ''}$${absDollars}`;
  };

  const getAccountIcon = (type: AccountType) => {
    switch (type) {
      case 'ASSET':
        return <Landmark className="w-4 h-4 text-emerald-400" />;
      case 'LIABILITY':
        return <Wallet className="w-4 h-4 text-cyan-400" />;
      case 'REVENUE':
        return <TrendingUp className="w-4 h-4 text-stripe-400" />;
      case 'EXPENSE':
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      default:
        return <ShieldCheck className="w-4 h-4 text-slate-400" />;
    }
  };

  const getTypeBadgeClass = (type: AccountType) => {
    switch (type) {
      case 'ASSET':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'LIABILITY':
        return 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20';
      case 'REVENUE':
        return 'bg-stripe-500/10 text-stripe-300 border-stripe-500/20';
      case 'EXPENSE':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
            <Landmark className="w-4 h-4 text-emerald-400" />
            Double-Entry T-Accounts &amp; Balance Inspector
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time computed ledger balances (Zero UPDATE balance queries - Append-Only).
          </p>
        </div>
        <div className="text-xs font-mono text-slate-400 bg-surface-base px-2.5 py-1 rounded border border-surface-border">
          {accounts.length} Ledgers Active
        </div>
      </div>

      {/* Grid of T-Accounts */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {accounts.map((acc) => {
          const isSelected = selectedAccountId === acc.id;
          const isAssetOrExpense = acc.type === 'ASSET' || acc.type === 'EXPENSE';

          return (
            <div
              key={acc.id}
              onClick={() => onSelectAccount?.(acc)}
              className={`rounded-xl border transition-all cursor-pointer p-4 flex flex-col justify-between ${
                isSelected
                  ? 'bg-surface-elevated border-stripe-500 shadow-lg shadow-stripe-500/10 ring-1 ring-stripe-500'
                  : 'bg-surface-base hover:bg-surface-elevated/70 border-surface-border'
              }`}
            >
              {/* Header */}
              <div>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${getTypeBadgeClass(acc.type)} flex items-center gap-1`}>
                    {getAccountIcon(acc.type)}
                    {acc.type}
                  </span>
                  <span className="text-[10px] font-mono text-slate-400 truncate max-w-[100px]">
                    {acc.id}
                  </span>
                </div>
                <h3 className="text-xs font-semibold text-slate-100 line-clamp-1">
                  {acc.name}
                </h3>
              </div>

              {/* T-Diagram Visualizer */}
              <div className="my-3 border-t-2 border-surface-subtle pt-1">
                <div className="grid grid-cols-2 text-center text-[10px] font-mono font-semibold uppercase text-slate-400 mb-1 border-b border-surface-border pb-1">
                  <div className="border-r border-surface-border pr-1">
                    Debit {isAssetOrExpense ? '(+)' : '(-)'}
                  </div>
                  <div className="pl-1">
                    Credit {isAssetOrExpense ? '(-)' : '(+)'}
                  </div>
                </div>
                <div className="text-center py-1">
                  <span className="text-[11px] font-mono text-slate-400">Normal Balance: </span>
                  <strong className="text-[11px] font-mono text-slate-200">
                    {isAssetOrExpense ? 'Debit' : 'Credit'}
                  </strong>
                </div>
              </div>

              {/* Live Computed Balance */}
              <div className="flex items-center justify-between pt-2 border-t border-surface-border">
                <span className="text-xs text-slate-400">Net Balance:</span>
                <span className={`text-sm font-mono font-bold ${
                  acc.balance_cents < 0 ? 'text-rose-400' : 'text-emerald-400'
                }`}>
                  {formatMoney(acc.balance_cents)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
