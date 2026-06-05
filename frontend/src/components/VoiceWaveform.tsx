'use client';

import React, { useState, useEffect } from 'react';
import { Mic, MicOff, Volume2 } from 'lucide-react';

interface VoiceWaveformProps {
  onSpeak?: (text: string) => void;
}

export default function VoiceWaveform({ onSpeak }: VoiceWaveformProps) {
  const [isListening, setIsListening] = useState(false);
  const [bars, setBars] = useState<number[]>([10, 10, 10, 10, 10, 10, 10, 10, 10, 10]);

  // Simulate audio amplitudes when listening
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isListening) {
      interval = setInterval(() => {
        setBars(
          Array.from({ length: 14 }, () => Math.floor(Math.random() * 35) + 5)
        );
      }, 90);
    } else {
      setBars(Array.from({ length: 14 }, () => 4));
    }
    return () => clearInterval(interval);
  }, [isListening]);

  const toggleVoice = () => {
    const nextState = !isListening;
    setIsListening(nextState);
    if (nextState) {
      // Simulate recruiter speaking to the assistant
      setTimeout(() => {
        setIsListening(false);
        if (onSpeak) {
          onSpeak('Tell me about Gradonix and book an interview');
        }
      }, 4000);
    }
  };

  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/40 p-4 backdrop-blur-md">
      <div className="flex items-center gap-4">
        {/* Toggle Button */}
        <button
          onClick={toggleVoice}
          aria-label={isListening ? 'Stop Voice Assistant' : 'Start Voice Assistant'}
          className={`relative flex h-12 w-12 items-center justify-center rounded-full transition-all duration-300 ${
            isListening
              ? 'bg-cyan-500 text-slate-950 shadow-[0_0_15px_rgba(6,182,212,0.5)] scale-105'
              : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
          }`}
        >
          {isListening ? (
            <Mic className="h-5 w-5 animate-pulse" />
          ) : (
            <Mic className="h-5 w-5" />
          )}

          {/* Outer Pulsing Rings */}
          {isListening && (
            <>
              <span className="absolute -inset-1 animate-ping rounded-full border border-cyan-500/30 opacity-75"></span>
              <span className="absolute -inset-3 animate-ping rounded-full border border-cyan-500/10 opacity-40"></span>
            </>
          )}
        </button>

        {/* Bouncing Audio Waveform */}
        <div className="flex h-10 items-center gap-1 px-2">
          {bars.map((height, i) => (
            <div
              key={i}
              className={`w-0.75 rounded-full transition-all duration-75 ${
                isListening ? 'bg-cyan-400' : 'bg-slate-700'
              }`}
              style={{
                height: `${height}px`,
              }}
            ></div>
          ))}
        </div>
      </div>

      <div className="text-center">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Voice Assistant
        </span>
        <p className="text-[11px] text-slate-400 mt-0.5">
          {isListening ? 'Listening to your question...' : 'Click mic to speak questions'}
        </p>
      </div>
    </div>
  );
}
