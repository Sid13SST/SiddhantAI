'use client';

import React, { useEffect, useRef } from 'react';
import { Citation } from '../types';
import { X, FileText, ExternalLink, Bookmark } from 'lucide-react';

interface EvidencePanelProps {
  isOpen: boolean;
  onClose: () => void;
  citations: Citation[];
  selectedIndex: number | null;
  onSelectCitation: (index: number | null) => void;
}

export default function EvidencePanel({
  isOpen,
  onClose,
  citations,
  selectedIndex,
  onSelectCitation,
}: EvidencePanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Scroll the selected citation card into view when selectedIndex changes
  useEffect(() => {
    if (selectedIndex !== null && containerRef.current) {
      const card = containerRef.current.querySelector(`[data-index="${selectedIndex}"]`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-slate-800 bg-slate-950/95 shadow-2xl backdrop-blur-xl transition-all duration-300 md:max-w-lg">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/40 px-4 py-4">
        <div className="flex items-center gap-2">
          <Bookmark className="h-5 w-5 text-cyan-400" />
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Grounded Evidence Panel</h2>
            <p className="text-[10px] text-slate-500 font-medium">Source verification ledger</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Citations List */}
      <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {citations.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center space-y-3">
            <FileText className="h-10 w-10 text-slate-700 animate-pulse" />
            <p className="text-xs text-slate-500">Ask a question to load source documents</p>
          </div>
        ) : (
          citations.map((citation) => {
            const isSelected = selectedIndex === citation.index;
            return (
              <div
                key={citation.index}
                data-index={citation.index}
                onClick={() => onSelectCitation(citation.index)}
                className={`group cursor-pointer rounded-xl border p-4 transition-all duration-300 ${
                  isSelected
                    ? 'border-cyan-500 bg-cyan-950/20 shadow-md shadow-cyan-500/5 ring-1 ring-cyan-500/30'
                    : 'border-slate-800 bg-slate-900/30 hover:border-slate-700 hover:bg-slate-900/50'
                }`}
              >
                {/* Badge Header */}
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold ${
                        isSelected ? 'bg-cyan-500 text-slate-950' : 'bg-slate-800 text-slate-300'
                      }`}
                    >
                      {citation.index}
                    </span>
                    <span className="text-xs font-semibold text-slate-300 group-hover:text-cyan-400 transition">
                      {citation.source}
                    </span>
                  </div>
                  <ExternalLink className="h-3 w-3 text-slate-600 group-hover:text-slate-400 transition" />
                </div>

                {/* Grounding Snippet */}
                <div className="rounded-lg bg-slate-950/60 p-3 border border-slate-850">
                  <p className="text-xs font-mono leading-relaxed text-slate-400 whitespace-pre-wrap">
                    {citation.snippet}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer Info */}
      <div className="border-t border-slate-800 bg-slate-950 px-4 py-3 text-center text-[10px] text-slate-500">
        All responses are mathematically grounded in the source documents to prevent hallucinations.
      </div>
    </div>
  );
}
