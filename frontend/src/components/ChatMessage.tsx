'use client';

import React from 'react';
import { Message, Citation } from '../types';
import { ShieldCheck, Bot, User, Sparkles } from 'lucide-react';

interface ChatMessageProps {
  message: Message;
  onCitationClick: (citation: Citation) => void;
}

export default function ChatMessage({ message, onCitationClick }: ChatMessageProps) {
  const { role, content, citations, sources, confidence, loading } = message;

  const renderParsedContent = (text: string) => {
    if (!text) return null;
    
    // Split by brackets to isolate citations, e.g. [Resume Page 1] or [1]
    const parts = text.split(/(\[[^\]]+\])/g);
    
    return parts.map((part, index) => {
      const isBracket = part.startsWith('[') && part.endsWith(']');
      if (isBracket) {
        const citationContent = part.slice(1, -1).trim();
        
        // Find matching citation by checking index, source name, or text token
        const citation = citations?.find(
          (c) =>
            c.index.toString() === citationContent ||
            c.source.toLowerCase().includes(citationContent.toLowerCase()) ||
            c.text.toLowerCase() === part.toLowerCase()
        );

        if (citation) {
          return (
            <button
              key={index}
              onClick={() => onCitationClick(citation)}
              className="mx-0.5 inline-flex h-4 items-center justify-center rounded bg-cyan-950/50 px-1.5 font-mono text-[9px] font-bold text-cyan-400 border border-cyan-800/40 hover:bg-cyan-500 hover:text-slate-950 transition active:scale-90"
              title={`View ground snippet from ${citation.source}`}
            >
              {citation.index}
            </button>
          );
        }
      }
      return <span key={index}>{part}</span>;
    });
  };

  const getSourceBadgeStyle = (src: string) => {
    const s = src.toLowerCase();
    if (s.includes('resume')) {
      return 'border-amber-500/30 bg-amber-950/20 text-amber-400 hover:bg-amber-950/40';
    }
    if (s.includes('readme')) {
      return 'border-teal-500/30 bg-teal-950/20 text-teal-400 hover:bg-teal-950/40';
    }
    if (s.includes('commit')) {
      return 'border-blue-500/30 bg-blue-950/20 text-blue-400 hover:bg-blue-950/40';
    }
    return 'border-violet-500/30 bg-violet-950/20 text-violet-400 hover:bg-violet-950/40'; // Code / default
  };

  return (
    <div
      className={`flex w-full gap-4 p-4 transition-all duration-300 ${
        role === 'user'
          ? 'justify-end bg-slate-950/10'
          : 'justify-start bg-slate-900/10 border-y border-slate-900/30'
      }`}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-xs font-semibold ${
          role === 'user'
            ? 'bg-slate-800 border-slate-700 text-slate-300'
            : 'bg-cyan-950/30 border-cyan-800/30 text-cyan-400 shadow-md shadow-cyan-950/20'
        }`}
      >
        {role === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble Wrapper */}
      <div className="flex max-w-2xl flex-col gap-2">
        {/* Header Metadata */}
        <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          <span>{role === 'user' ? 'Recruiter' : 'Siddhant AI'}</span>
          <span>•</span>
          <span>{message.timestamp}</span>

          {role === 'assistant' && confidence !== undefined && confidence > 0 && (
            <>
              <span>•</span>
              <span className="flex items-center gap-0.5 text-emerald-500">
                <ShieldCheck className="h-3 w-3" />
                Grounding Confidence: {Math.round(confidence * 100)}%
              </span>
            </>
          )}
        </div>

        {/* Content bubble */}
        <div
          className={`text-sm leading-relaxed text-slate-200 whitespace-pre-wrap ${
            role === 'user' ? 'font-medium' : 'font-normal'
          }`}
        >
          {loading ? (
            <div className="flex items-center gap-1 py-1.5">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-400" style={{ animationDelay: '0ms' }}></span>
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-400" style={{ animationDelay: '150ms' }}></span>
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-400" style={{ animationDelay: '300ms' }}></span>
            </div>
          ) : (
            renderParsedContent(content)
          )}
        </div>

        {/* Source Badges */}
        {role === 'assistant' && sources && sources.length > 0 && !loading && (
          <div className="mt-2 flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mr-1">Sources:</span>
            {sources.map((src) => (
              <span
                key={src}
                className={`rounded border px-2 py-0.5 text-[9px] font-semibold transition duration-200 ${getSourceBadgeStyle(
                  src
                )}`}
              >
                {src}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
