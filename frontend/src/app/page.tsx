'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../hooks/useChat';
import TrustIndicator from '../components/TrustIndicator';
import Suggestions from '../components/Suggestions';
import ChatMessage from '../components/ChatMessage';
import BookingCard from '../components/BookingCard';
import VoiceWaveform from '../components/VoiceWaveform';
import EvidencePanel from '../components/EvidencePanel';
import {
  MessageSquare,
  Sparkles,
  Send,
  Trash2,
  Mic,
  Calendar,
  VolumeX,
  Compass,
  FileCode2,
} from 'lucide-react';

export default function Home() {
  const {
    messages,
    isTyping,
    currentTopic,
    currentBookingContext,
    evidenceOpen,
    setEvidenceOpen,
    activeEvidence,
    selectedCitationIndex: selectedIndex,
    setSelectedCitationIndex,
    error,
    sendMessage,
    clearChat,
  } = useChat();

  const [inputText, setInputText] = useState('');
  const [showVoice, setShowVoice] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom of messages container
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (inputText.trim()) {
      sendMessage(inputText.trim());
      setInputText('');
    }
  };

  const handleSuggestionSelect = (text: string) => {
    sendMessage(text);
  };

  const handleVoiceSpeak = (text: string) => {
    sendMessage(text);
    setShowVoice(false);
  };

  return (
    <main className="relative flex h-screen w-screen overflow-hidden bg-slate-950 font-sans text-slate-100 antialiased">
      {/* Background glowing overlays */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none opacity-40">
        <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl pulsing-glow"></div>
        <div className="absolute top-1/2 -right-40 h-[500px] w-[500px] rounded-full bg-violet-500/5 blur-3xl pulsing-glow" style={{ animationDelay: '2s' }}></div>
      </div>

      {/* Main Container */}
      <div className="relative z-10 flex flex-1 flex-col md:flex-row h-full w-full">
        {/* Chat Feed Panel */}
        <div className="flex flex-1 flex-col h-full overflow-hidden border-slate-900">
          {/* Header Panel */}
          <header className="flex shrink-0 items-center justify-between border-b border-slate-900 bg-slate-950/80 px-6 py-4 backdrop-blur-md">
            <div className="flex items-center gap-3">
              <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-950/20 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.15)]">
                <Sparkles className="h-5 w-5" />
                <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                </span>
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-slate-100 md:text-base">
                  Siddhant AI Persona
                </h1>
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                  Official Digital Representative
                </p>
              </div>
            </div>

            {/* Middle Status Indicators */}
            <div className="hidden items-center gap-3 md:flex">
              {/* Topic Memory Indicator */}
              <div className="flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/40 px-3 py-1 text-xs">
                <Compass className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  Conversation Context:
                </span>
                <span className="font-semibold text-slate-300">{currentTopic}</span>
              </div>

              {/* Evidence Trigger Button */}
              {activeEvidence.length > 0 && (
                <button
                  onClick={() => setEvidenceOpen(!evidenceOpen)}
                  className="flex items-center gap-1.5 rounded-full border border-cyan-800/40 bg-cyan-950/10 px-3 py-1 text-xs font-semibold text-cyan-400 hover:bg-cyan-500 hover:text-slate-950 transition"
                >
                  <FileCode2 className="h-3.5 w-3.5" />
                  <span>Show Evidence Ledger ({activeEvidence.length})</span>
                </button>
              )}
            </div>

            {/* Right Buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={clearChat}
                title="Reset Conversation"
                className="rounded-lg p-2 text-slate-500 border border-transparent hover:border-slate-800 hover:bg-slate-900/50 hover:text-slate-200 transition"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </header>

          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto bg-slate-950/20 scrollbar-thin">
            {messages.length === 0 ? (
              /* Landing Screen (First Load) */
              <div className="mx-auto flex max-w-2xl flex-col items-center justify-center py-12 px-6 space-y-8">
                {/* Greeting Hero */}
                <div className="text-center space-y-3">
                  <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 mb-2">
                    <MessageSquare className="h-6 w-6" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-100 tracking-tight">
                    Welcome to Siddhant AI
                  </h2>
                  <p className="mx-auto max-w-md text-xs leading-relaxed text-slate-400">
                    Ask me about career history, technical stack (Python, FastAPI, Next.js), source code implementation, or schedule an interview slot.
                  </p>
                </div>

                {/* Grounded Trust Indicator Bar */}
                <div className="w-full">
                  <TrustIndicator />
                </div>

                {/* Suggestions List */}
                <div className="w-full">
                  <Suggestions onSelect={handleSuggestionSelect} />
                </div>
              </div>
            ) : (
              /* Active Chat Feed */
              <div className="flex flex-col">
                {messages.map((msg, i) => (
                  <div key={msg.id || i}>
                    <ChatMessage
                      message={msg}
                      onCitationClick={(cit) => {
                        setSelectedCitationIndex(cit.index);
                        setEvidenceOpen(true);
                      }}
                    />

                    {/* Inline booking slots card injection */}
                    {i === messages.length - 1 &&
                      msg.role === 'assistant' &&
                      currentBookingContext.step !== 'none' && (
                        <div className="mx-auto max-w-2xl px-16 pb-4">
                          <BookingCard
                            context={currentBookingContext}
                            onAction={(val) => sendMessage(val)}
                          />
                        </div>
                      )}
                  </div>
                ))}
                {isTyping && messages[messages.length - 1]?.role === 'user' && (
                  <ChatMessage
                    message={{
                      id: 'typing_indicator',
                      role: 'assistant',
                      content: '',
                      timestamp: '',
                      loading: true,
                    }}
                    onCitationClick={() => {}}
                  />
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Network Error Display */}
          {error && (
            <div className="mx-auto max-w-2xl px-6 py-2">
              <div className="rounded-lg bg-rose-950/20 border border-rose-500/30 p-3 text-xs text-rose-400 text-center">
                {error}
              </div>
            </div>
          )}

          {/* Mobile indicator pill bar */}
          <div className="flex items-center justify-between border-t border-slate-900 bg-slate-950 px-6 py-2 md:hidden">
            <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">
              Topic: {currentTopic}
            </span>
            {activeEvidence.length > 0 && (
              <button
                onClick={() => setEvidenceOpen(!evidenceOpen)}
                className="text-[9px] font-bold text-cyan-400 uppercase tracking-widest"
              >
                Citations ({activeEvidence.length})
              </button>
            )}
          </div>

          {/* Footer Input Bar */}
          <div className="border-t border-slate-900 bg-slate-950/60 p-4 backdrop-blur-md">
            <div className="mx-auto max-w-3xl space-y-4">
              {/* Voice panel popover */}
              {showVoice && (
                <div className="w-full">
                  <VoiceWaveform onSpeak={handleVoiceSpeak} />
                </div>
              )}

              {/* Text Input Row */}
              <form onSubmit={handleSend} className="relative flex items-center gap-2">
                {/* Voice Toggle Button */}
                <button
                  type="button"
                  onClick={() => setShowVoice(!showVoice)}
                  className={`rounded-xl border p-3 transition active:scale-95 ${
                    showVoice
                      ? 'border-cyan-500/50 bg-cyan-950/20 text-cyan-400'
                      : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-white'
                  }`}
                  title="Voice Input Mode"
                >
                  <Mic className="h-5 w-5" />
                </button>

                {/* Input Field */}
                <input
                  type="text"
                  placeholder={
                    currentBookingContext.step !== 'none'
                      ? 'Select option above or reply here...'
                      : 'Ask me anything about Siddhant...'
                  }
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  className="flex-1 rounded-xl border border-slate-800 bg-slate-900/40 py-3 pr-12 pl-4 text-sm text-slate-200 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 transition duration-300"
                />

                {/* Send Button */}
                <button
                  type="submit"
                  disabled={!inputText.trim() || isTyping}
                  className="absolute right-2.5 top-2 rounded-lg bg-cyan-500 p-1.5 text-slate-950 hover:bg-cyan-400 disabled:opacity-40 transition"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* Evidence Slide-over Sidebar Drawer */}
        <EvidencePanel
          isOpen={evidenceOpen}
          onClose={() => setEvidenceOpen(false)}
          citations={activeEvidence}
          selectedIndex={selectedIndex}
          onSelectCitation={(idx) => setSelectedCitationIndex(idx)}
        />
      </div>
    </main>
  );
}
