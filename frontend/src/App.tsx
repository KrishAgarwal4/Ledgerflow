import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { TimeScrubber } from './components/TimeScrubber';
import { TAccountViewer } from './components/TAccountViewer';
import { JournalInspector } from './components/JournalInspector';
import { BillingPanel } from './components/BillingPanel';
import { ChaosTester } from './components/ChaosTester';
import { api } from './api/client';
import {
  Account, JournalEntry, GlobalLedgerVerification,
  Customer, Plan, Invoice, TestClock, ClockMilestone
} from './types';
import { Landmark, Users, Zap, BookOpen, Layers, CheckCircle2, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  // Navigation Tabs
  const [activeTab, setActiveTab] = useState<'ledger' | 'billing' | 'chaos'>('ledger');

  // Core State
  const [clock, setClock] = useState<TestClock | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [verification, setVerification] = useState<GlobalLedgerVerification | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);

  // Loading States
  const [isLoading, setIsLoading] = useState(true);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [selectedAccountId, setSelectedAccountId] = useState<string | undefined>(undefined);

  // Fetch all state
  const refreshData = useCallback(async () => {
    try {
      const [
        clockData,
        accountsData,
        entriesData,
        verifyData,
        customersData,
        plansData,
        invoicesData
      ] = await Promise.all([
        api.getClock(),
        api.getAccounts(),
        api.getJournalEntries(50),
        api.verifyLedger(),
        api.getCustomers(),
        api.getPlans(),
        api.getInvoices(),
      ]);

      setClock(clockData);
      setAccounts(accountsData);
      setJournalEntries(entriesData);
      setVerification(verifyData);
      setCustomers(customersData);
      setPlans(plansData);
      setInvoices(invoicesData);
    } catch (err) {
      console.error('Failed to load Chronos data:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  // Advance Virtual Clock
  const handleAdvanceClock = async (seconds: number) => {
    setIsAdvancing(true);
    try {
      const updatedClock = await api.advanceClock(seconds);
      setClock(updatedClock);
      await refreshData();
    } catch (err: any) {
      alert(`Advancement error: ${err.message}`);
    } finally {
      setIsAdvancing(false);
    }
  };

  // Reset Environment
  const handleReset = async () => {
    if (!window.confirm('Reset database back to canonical seeded state? All simulated invoices and journal entries will be restored to initial balances.')) {
      return;
    }
    setIsResetting(true);
    try {
      const freshClock = await api.resetEnvironment();
      setClock(freshClock);
      await refreshData();
    } catch (err: any) {
      alert(`Reset error: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  const formatMoney = (cents: number) => `$${(cents / 100).toFixed(2)}`;

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col">
      {/* Stripe-Grade Top Bar */}
      <Header
        clock={clock}
        verification={verification}
        onReset={handleReset}
        isResetting={isResetting}
        isAdvancing={isAdvancing}
      />

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">
        
        {/* Virtual Time Scrubber */}
        <TimeScrubber
          currentVirtualTime={clock?.current_virtual_time}
          milestones={clock?.milestones || []}
          onAdvance={handleAdvanceClock}
          isAdvancing={isAdvancing}
        />

        {/* Navigation Tabs Bar */}
        <div className="flex items-center justify-between border-b border-surface-border pb-1">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('ledger')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                activeTab === 'ledger'
                  ? 'bg-stripe-600 text-white shadow-lg shadow-stripe-600/30'
                  : 'text-slate-400 hover:text-white hover:bg-surface-elevated'
              }`}
            >
              <Landmark className="w-4 h-4" />
              T-Account Ledger &amp; Journal
            </button>

            <button
              onClick={() => setActiveTab('billing')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                activeTab === 'billing'
                  ? 'bg-stripe-600 text-white shadow-lg shadow-stripe-600/30'
                  : 'text-slate-400 hover:text-white hover:bg-surface-elevated'
              }`}
            >
              <Users className="w-4 h-4" />
              Subscriptions, Invoices &amp; Proration
            </button>

            <button
              onClick={() => setActiveTab('chaos')}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition-all ${
                activeTab === 'chaos'
                  ? 'bg-gradient-to-r from-amber-600 to-rose-600 text-white shadow-lg shadow-rose-600/20'
                  : 'text-slate-400 hover:text-white hover:bg-surface-elevated'
              }`}
            >
              <Zap className="w-4 h-4 text-amber-300" />
              Chaos &amp; Concurrency Stress Tester
            </button>
          </div>

          {/* Quick Ledger Balance Check */}
          {verification && (
            <div className="hidden lg:flex items-center gap-2 font-mono text-[11px] text-slate-400">
              <span>Total Debits: <strong className="text-white">{formatMoney(verification.total_debits_cents)}</strong></span>
              <span className="text-slate-600">|</span>
              <span>Total Credits: <strong className="text-white">{formatMoney(verification.total_credits_cents)}</strong></span>
            </div>
          )}
        </div>

        {/* Tab Panes */}
        {activeTab === 'ledger' && (
          <div className="space-y-6">
            <TAccountViewer
              accounts={accounts}
              selectedAccountId={selectedAccountId}
              onSelectAccount={(acc) => setSelectedAccountId(selectedAccountId === acc.id ? undefined : acc.id)}
            />
            <JournalInspector
              entries={journalEntries}
              highlightAccountId={selectedAccountId}
            />
          </div>
        )}

        {activeTab === 'billing' && (
          <BillingPanel
            customers={customers}
            plans={plans}
            invoices={invoices}
            onRefresh={refreshData}
          />
        )}

        {activeTab === 'chaos' && (
          <ChaosTester
            onRefresh={refreshData}
            virtualTime={clock?.current_virtual_time}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-surface-border bg-surface-card py-4 px-6 text-center text-xs text-slate-400 font-mono">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>CHRONOS — Full-Stack Immutable Double-Entry Ledger &amp; Billing Simulator</span>
          <span>Zero UPDATE Balance Queries &bull; ACID Concurrency &bull; Integer Cents Math</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
