'use client';

import React from 'react';
import { Headphones, PhoneCall } from 'lucide-react';

interface VoiceAssistantButtonProps {
  onClick: () => void;
}

export default function VoiceAssistantButton({ onClick }: VoiceAssistantButtonProps) {
  return (
    <button
      onClick={onClick}
      aria-label="Open Voice Call Assistant"
      className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20 transition-all duration-300 hover:scale-110 hover:bg-cyan-400 hover:shadow-cyan-500/40 active:scale-95 group"
    >
      <Headphones className="h-6 w-6 group-hover:hidden transition duration-300" />
      <PhoneCall className="h-6 w-6 hidden group-hover:block transition duration-300 animate-pulse" />
      
      {/* Outer Pulse rings */}
      <span className="absolute -inset-1 animate-ping rounded-full border border-cyan-500/20 opacity-40"></span>
    </button>
  );
}
