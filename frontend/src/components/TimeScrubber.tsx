import React, { useState } from 'react';
import { FastForward, Clock, Calendar, ChevronRight, Activity, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';
import { ClockMilestone } from '../types';

interface TimeScrubberProps {
  currentVirtualTime?: string;
  milestones: ClockMilestone[];
  onAdvance: (seconds: number) => Promise<void>;
  isAdvancing: boolean;
}

export const TimeScrubber: React.FC<TimeScrubberProps> = ({
  currentVirtualTime,
  milestones,
  onAdvance,
  isAdvancing,
}) => {
  const [selectedMilestone, setSelectedMilestone] = useState<ClockMilestone | null>(null);

  const quickJumps = [
    { label: '+1 Hour', seconds: 3600, hint: 'Emit Hourly Usage' },
    { label: '+1 Day', seconds: 86400, hint: 'Advance 24h' },
    { label: '+3 Days', seconds: 259200, hint: 'Trigger Dunning Retry #2' },
    { label: '+7 Days', seconds: 604800, hint: 'Final Dunning Backoff' },
    { label: '+30 Days', seconds: 2592000, hint: 'Close Cycle & Invoices' },
  ];

  const getMilestoneBadge = (eventType: string) => {
    if (eventType.includes('PAID') || eventType.includes('RECOVERED')) {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
          {eventType}
        </span>
      );
    }
    if (eventType.includes('FAILED') || eventType.includes('PAST_DUE')) {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <AlertCircle className="w-3 h-3 text-amber-400" />
          {eventType}
        </span>
      );
    }
    if (eventType.includes('CANCELED')) {
      return (
        <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <XCircle className="w-3 h-3 text-rose-400" />
          {eventType}
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded-full bg-stripe-500/10 text-stripe-300 border border-stripe-500/20">
        <Activity className="w-3 h-3 text-stripe-400" />
        {eventType}
      </span>
    );
  };

  return (
    <div className="bg-surface-card border border-surface-border rounded-xl p-5 shadow-xl">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-white uppercase flex items-center gap-2">
            <FastForward className="w-4 h-4 text-stripe-400" />
            Deterministic Time Travel Engine
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Sweeps chronological milestones, down-to-the-second proration, and dunning state retries.
          </p>
        </div>

        {/* Quick Jump Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          {quickJumps.map((jump) => (
            <button
              key={jump.label}
              onClick={() => onAdvance(jump.seconds)}
              disabled={isAdvancing}
              className="group flex flex-col items-start px-3 py-1.5 rounded-lg bg-surface-elevated hover:bg-stripe-600/20 hover:border-stripe-500/50 border border-surface-border text-xs transition-all disabled:opacity-50"
            >
              <span className="font-semibold text-slate-200 group-hover:text-white flex items-center gap-1">
                {jump.label}
              </span>
              <span className="text-[10px] text-slate-400 group-hover:text-stripe-300 font-mono">
                {jump.hint}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Discrete Simulation Milestones Timeline Feed */}
      <div className="border-t border-surface-border pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase text-slate-400 font-mono flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-stripe-400" />
            Discrete Event Log ({milestones.length} Milestones Triggered)
          </span>
          <span className="text-[11px] text-slate-400">
            Chronological deterministic audit
          </span>
        </div>

        {milestones.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-surface-border rounded-lg bg-surface-base/50">
            <Clock className="w-6 h-6 text-slate-400 mx-auto mb-2" />
            <p className="text-xs text-slate-400">
              No milestones simulated yet. Click a time travel jump (e.g. <strong>+30 Days</strong>) to close billing cycles and fire retries.
            </p>
          </div>
        ) : (
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {milestones.map((ms) => (
              <div
                key={ms.id}
                onClick={() => setSelectedMilestone(selectedMilestone?.id === ms.id ? null : ms)}
                className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                  selectedMilestone?.id === ms.id
                    ? 'bg-surface-elevated border-stripe-500/50 shadow-md'
                    : 'bg-surface-base/80 hover:bg-surface-elevated/50 border-surface-border'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    {getMilestoneBadge(ms.event_type)}
                    <span className="font-medium text-slate-200">
                      {ms.description}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                    <span>{new Date(ms.timestamp).toISOString().slice(0, 19).replace('T', ' ')} UTC</span>
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform ${selectedMilestone?.id === ms.id ? 'rotate-90' : ''}`} />
                  </div>
                </div>

                {selectedMilestone?.id === ms.id && ms.details_json && (
                  <div className="mt-2.5 pt-2 border-t border-surface-border/60">
                    <div className="text-[11px] font-mono text-slate-400 mb-1">State Transition Payload:</div>
                    <pre className="p-2 rounded bg-black/40 text-[11px] font-mono text-slate-300 overflow-x-auto">
                      {JSON.stringify(ms.details_json, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
