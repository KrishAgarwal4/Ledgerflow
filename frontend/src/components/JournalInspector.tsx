import React, { useState } from 'react';
import { JournalEntry, LedgerPosting } from '../types';
import { BookOpen, CheckCircle, Key, ChevronDown, ChevronUp, Hash } from 'lucide-react';

interface JournalInspectorProps {
  entries: JournalEntry[];
  highlightAccountId?: string;
}

export const JournalInspector: React.FC<JournalInspectorProps> = ({
  entries,
  highlightAccountId,
}) => {
  const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);

  const formatMoney = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-stripe-400" />
            Append-Only Journal Entries &amp; Postings
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Every transaction is mathematically balanced: SUM(DEBIT) == SUM(CREDIT).
          </p>
        </div>
        <div className="text-xs font-mono text-slate-400 bg-surface-base px-2.5 py-1 rounded border border-surface-border">
          {entries.length} Logged Entries
        </div>
      </div>

      {entries.length === 0 ? (
        <div className="text-center py-8 text-xs text-slate-400 border border-dashed border-surface-border rounded-lg">
          No journal entries recorded yet.
        </div>
      ) : (
        <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
          {entries.map((entry) => {
            const isExpanded = expandedEntryId === entry.id;
            const debits = entry.postings.filter((p) => p.direction === 'DEBIT');
            const credits = entry.postings.filter((p) => p.direction === 'CREDIT');
            const totalDebit = debits.reduce((acc, p) => acc + p.amount_cents, 0);
            const totalCredit = credits.reduce((acc, p) => acc + p.amount_cents, 0);
            const isBalanced = totalDebit === totalCredit;

            return (
              <div
                key={entry.id}
                className="border border-surface-border bg-surface-base rounded-xl overflow-hidden transition-all hover:border-surface-subtle"
              >
                {/* Entry Summary Bar */}
                <div
                  onClick={() => setExpandedEntryId(isExpanded ? null : entry.id)}
                  className="p-3.5 flex items-center justify-between gap-4 cursor-pointer hover:bg-surface-elevated/40"
                >
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                      <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    </span>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-slate-100">
                          {entry.description}
                        </span>
                        {entry.idempotency_key && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-stripe-500/10 text-stripe-300 border border-stripe-500/20 flex items-center gap-1">
                            <Key className="w-2.5 h-2.5" />
                            {entry.idempotency_key.slice(0, 14)}...
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        Effective: {new Date(entry.effective_at).toISOString().slice(0, 19).replace('T', ' ')} UTC
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 text-right">
                    <div>
                      <span className="text-xs font-mono font-bold text-white">
                        {formatMoney(totalDebit)}
                      </span>
                      <div className="text-[10px] font-mono text-emerald-400">
                        {isBalanced ? 'Balanced 0¢ Delta' : 'UNBALANCED'}
                      </div>
                    </div>
                    {isExpanded ? (
                      <ChevronUp className="w-4 h-4 text-slate-400" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-slate-400" />
                    )}
                  </div>
                </div>

                {/* Expanded Postings Table */}
                {isExpanded && (
                  <div className="border-t border-surface-border bg-surface-card/60 p-4">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2 font-mono flex items-center gap-1">
                      <Hash className="w-3 h-3 text-slate-400" />
                      Double-Entry Postings Breakdown:
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                      {/* Debits Column */}
                      <div className="p-2.5 rounded-lg bg-emerald-950/20 border border-emerald-500/20">
                        <div className="text-[11px] font-mono font-bold text-emerald-400 uppercase mb-1.5">
                          DEBIT POSTINGS (+)
                        </div>
                        {debits.map((p) => (
                          <div
                            key={p.id}
                            className={`flex items-center justify-between text-xs py-1 border-b border-emerald-950/40 last:border-0 ${
                              highlightAccountId === p.account_id ? 'font-bold text-white bg-emerald-500/20 px-1 rounded' : 'text-slate-300'
                            }`}
                          >
                            <span className="font-mono text-[11px]">{p.account_id}</span>
                            <span className="font-mono font-semibold text-emerald-400">{formatMoney(p.amount_cents)}</span>
                          </div>
                        ))}
                      </div>

                      {/* Credits Column */}
                      <div className="p-2.5 rounded-lg bg-cyan-950/20 border border-cyan-500/20">
                        <div className="text-[11px] font-mono font-bold text-cyan-400 uppercase mb-1.5">
                          CREDIT POSTINGS (-)
                        </div>
                        {credits.map((p) => (
                          <div
                            key={p.id}
                            className={`flex items-center justify-between text-xs py-1 border-b border-cyan-950/40 last:border-0 ${
                              highlightAccountId === p.account_id ? 'font-bold text-white bg-cyan-500/20 px-1 rounded' : 'text-slate-300'
                            }`}
                          >
                            <span className="font-mono text-[11px]">{p.account_id}</span>
                            <span className="font-mono font-semibold text-cyan-400">{formatMoney(p.amount_cents)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {entry.metadata_json && Object.keys(entry.metadata_json).length > 0 && (
                      <div className="pt-2 border-t border-surface-border">
                        <span className="text-[10px] font-mono text-slate-400">Metadata: </span>
                        <code className="text-[10px] font-mono text-slate-300">
                          {JSON.stringify(entry.metadata_json)}
                        </code>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
