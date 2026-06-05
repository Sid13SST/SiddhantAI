import React from 'react';
import { ShieldCheck, GitBranch, Terminal, FileCheck } from 'lucide-react';

export default function TrustIndicator() {
  const items = [
    { label: 'Resume Data', icon: FileCheck, color: 'text-amber-400' },
    { label: 'GitHub Profile', icon: GitBranch, color: 'text-teal-400' },
    { label: 'Commit History', icon: Terminal, color: 'text-blue-400' },
    { label: 'Source Code', icon: ShieldCheck, color: 'text-cyan-400' },
  ];

  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-slate-800 bg-slate-900/40 p-3.5 text-center backdrop-blur-md">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
        Grounded Trust Verification Ledger
      </span>
      <div className="flex flex-wrap items-center justify-center gap-4 mt-1">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex items-center gap-1.5 text-xs text-slate-300">
              <Icon className={`h-3.5 w-3.5 ${item.color}`} />
              <span className="font-semibold">{item.label}</span>
              <span className="text-[10px] text-emerald-400 font-bold">✓</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
