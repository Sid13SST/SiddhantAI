'use client';

import React from 'react';
import { User, Bot } from 'lucide-react';

interface TranscriptItem {
  role: 'user' | 'assistant';
  content: string;
  corrected?: string;
}

interface VoiceTranscriptProps {
  history: TranscriptItem[];
}

export default function VoiceTranscript({ history }: VoiceTranscriptProps) {
  if (history.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <span className="h-2 w-2 animate-ping rounded-full bg-cyan-400"></span>
        <p className="text-xs text-slate-500 mt-2 font-medium">Waiting for call connection...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 max-h-48 overflow-y-auto px-1 py-2 scrollbar-thin">
      {history.map((item, idx) => {
        const isUser = item.role === 'user';
        return (
          <div
            key={idx}
            className={`flex items-start gap-2 text-xs ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            {!isUser && (
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-cyan-950/40 border border-cyan-800/30 text-cyan-400">
                <Bot className="h-3 w-3" />
              </div>
            )}
            <div className="max-w-[80%] flex flex-col gap-0.5">
              <div
                className={`rounded-lg px-2.5 py-1.5 leading-normal ${
                  isUser
                    ? 'bg-slate-800 text-slate-200 rounded-tr-none'
                    : 'bg-slate-900/60 border border-slate-800 text-slate-300 rounded-tl-none'
                }`}
              >
                <p>{item.content}</p>
              </div>
              {isUser && item.corrected && item.corrected.toLowerCase() !== item.content.toLowerCase() && (
                <span className="text-[9px] font-mono text-cyan-500/80 mt-0.5 self-end">
                  * Phonetic Correction: "{item.corrected}"
                </span>
              )}
            </div>
            {isUser && (
              <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-800 border border-slate-700 text-slate-400">
                <User className="h-3 w-3" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
