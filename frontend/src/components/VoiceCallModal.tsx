'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Phone, PhoneOff, Mic, MicOff, Volume2, VolumeX, Sparkles, Award, FileText, CheckCircle, Clock } from 'lucide-react';
import VoiceTranscript from './VoiceTranscript';
import { API_BASE } from '../services/api';

interface VoiceCallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CallSummary {
  call_id: string;
  call_duration: string;
  topics_discussed: string[];
  booking_created: boolean;
  booking_id: string | null;
  cancellation_completed: boolean;
  timestamp: string;
}

export default function VoiceCallModal({ isOpen, onClose }: VoiceCallModalProps) {
  const [callState, setCallState] = useState<'idle' | 'connecting' | 'active' | 'ended' | 'error'>('idle');
  const [isMuted, setIsMuted] = useState(false);
  const [callId, setCallId] = useState<string>('');
  const [activeTopic, setActiveTopic] = useState<string>('General QA');
  const [transcript, setTranscript] = useState<{ role: 'user' | 'assistant'; content: string; corrected?: string }[]>([]);
  const [summary, setSummary] = useState<CallSummary | null>(null);
  const [pulseCount, setPulseCount] = useState<number[]>([1, 1, 1]);

  const vapiRef = useRef<any>(null);
  const simulatedCallIdRef = useRef<string>('');
  const callStartRef = useRef<number>(0);
  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<any>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      synthRef.current = window.speechSynthesis;
    }
  }, []);

  // Pulsing animation rings
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (callState === 'active') {
      interval = setInterval(() => {
        setPulseCount((prev) => prev.map(() => Math.random() * 0.4 + 0.8));
      }, 600);
    } else {
      setPulseCount([1, 1, 1]);
    }
    return () => clearInterval(interval);
  }, [callState]);

  if (!isOpen) return null;

  // Initialize Vapi SDK Client if API Key is available
  const startVapiCall = async (publicKey: string, assistantId: string) => {
    try {
      const Vapi = (await import('@vapi-ai/web')).default;
      const vapi = new Vapi(publicKey);
      vapiRef.current = vapi;

      setCallState('connecting');
      vapi.start(assistantId);

      vapi.on('call-start', () => {
        setCallState('active');
        setCallId((vapi as any).getCallId?.() || `voice_${Math.random().toString(36).substring(7)}`);
        setTranscript([
          { role: 'assistant', content: "Hello, I am Siddhant's voice representative. How can I help you today?" }
        ]);
      });

      vapi.on('call-end', async () => {
        setCallState('ended');
        // Fetch summary from backend which Vapi hits via webhook
        await fetchCallSummary((vapi as any).getCallId?.());
      });

      vapi.on('message', (message: any) => {
        if (message.type == 'transcript' && message.transcriptType == 'final') {
          const role = message.role === 'assistant' ? 'assistant' : 'user';
          setTranscript((prev) => [...prev, { role, content: message.transcript }]);
          // Fetch current active topic from backend
          const callIdVal = (vapi as any).getCallId?.();
          if (callIdVal) {
            fetch(`${API_BASE}/api/v1/voice/session?session_id=${callIdVal}`)
              .then((res) => res.json())
              .then((data) => {
                setActiveTopic(data.active_topic || 'General QA');
              })
              .catch(() => {});
          }
        }
      });

      vapi.on('error', (err: any) => {
        console.error('Vapi Error:', err);
        setCallState('error');
      });
    } catch (e) {
      console.error('Failed to start Vapi call:', e);
      setCallState('error');
    }
  };

  // Graceful Web Speech API Telephony Simulator (If Vapi keys are unconfigured)
  const startSimulatedCall = () => {
    setCallState('connecting');
    const simCallId = `voice_${Math.random().toString(36).substring(2, 14)}`;
    simulatedCallIdRef.current = simCallId;
    setCallId(simCallId);
    callStartRef.current = Date.now();

    // Trigger initial Greeting
    setTimeout(() => {
      setCallState('active');
      const welcome = "Hello, I am Siddhant's voice representative. How can I help you today?";
      setTranscript([{ role: 'assistant', content: welcome }]);
      speakText(welcome);
      
      // Initialize speech recognition
      startRecognition();
    }, 1200);
  };

  const handleUserUtterance = async (resultText: string) => {
    if (!resultText || !resultText.trim()) return;

    // Add user speech to transcript
    setTranscript((prev) => [...prev, { role: 'user', content: resultText }]);

    // POST user utterance to completions endpoint
    try {
      const res = await fetch(`${API_BASE}/api/v1/voice/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-vapi-call-id': simulatedCallIdRef.current
        },
        body: JSON.stringify({
          model: 'google/gemini-2.5-flash',
          messages: [
            { role: 'user', content: resultText }
          ]
        })
      });

      if (!res.ok) throw new Error('API completion call failed');
      const data = await res.json();
      const assistantReply = data.choices[0].message.content;

      // Fetch session update to sync topic and corrections
      const sessRes = await fetch(`${API_BASE}/api/v1/voice/session?session_id=${simulatedCallIdRef.current}`);
      if (sessRes.ok) {
        const sessData = await sessRes.json();
        setActiveTopic(sessData.active_topic);
        // Sync phonetic corrections if any
        const lastUserTurn = sessData.history[sessData.history.length - 2];
        if (lastUserTurn) {
          setTranscript((prev) => {
            const next = [...prev];
            const userIdx = next.map(t => t.role).lastIndexOf('user');
            if (userIdx !== -1) {
              next[userIdx].corrected = lastUserTurn.corrected;
            }
            return next;
          });
        }
      }

      // Add assistant reply and speak it
      setTranscript((prev) => [...prev, { role: 'assistant', content: assistantReply }]);
      speakText(assistantReply);

    } catch (err) {
      console.error('Simulated query completions fail:', err);
      const errReply = "I am sorry, but there was an error processing your query.";
      setTranscript((prev) => [...prev, { role: 'assistant', content: errReply }]);
      speakText(errReply);
    }
  };

  const startRecognition = () => {
    if (typeof window === 'undefined') return;
    
    // Check Web Speech API support
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.error('Browser does not support SpeechRecognition');
      setCallState('error');
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = 'en-US';

    rec.onresult = (event: any) => {
      const resultText = event.results[0][0].transcript;
      handleUserUtterance(resultText);
    };

    rec.onend = () => {
      // Keep listening if call is active and user is not muted
      if (callState === 'active' && !isMuted) {
        try {
          rec.start();
        } catch (e) {}
      }
    };

    recognitionRef.current = rec;
    rec.start();
  };

  const speakText = (text: string) => {
    if (!synthRef.current || isMuted) return;
    
    // Stop any active speech first
    synthRef.current.cancel();

    // Clean markdown characters from TTS output
    const cleanText = text.replace(/[*#`_\-]/g, '').replace(/\[\d+\]/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    // Resume speech recognition once TTS ends
    utterance.onend = () => {
      if (callState === 'active' && recognitionRef.current) {
        try {
          recognitionRef.current.start();
        } catch (e) {}
      }
    };

    // Pause speech recognition while speaking to prevent echo feedback loop
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
    }

    synthRef.current.speak(utterance);
  };

  const fetchCallSummary = async (cid: string) => {
    try {
      // Query summaries json list
      const res = await fetch(`${API_BASE}/api/v1/voice/session?session_id=${cid}`);
      if (res.ok) {
        // Retrieve session history
        const sessData = await res.json();
        // Since Vapi might still be compiling summary, let's call our mock summary generator
        // In the simulator call, we call our own endpoint
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleStartCall = () => {
    const publicKey = process.env.NEXT_PUBLIC_VAPI_PUBLIC_KEY;
    const assistantId = process.env.NEXT_PUBLIC_VAPI_ASSISTANT_ID;

    setSummary(null);
    setTranscript([]);
    setActiveTopic('General QA');

    if (publicKey && assistantId) {
      startVapiCall(publicKey, assistantId);
    } else {
      logger.info("Keys absent. Initializing Web Speech simulator.");
      startSimulatedCall();
    }
  };

  const handleEndCall = async () => {
    // End speech recognition and synth
    if (recognitionRef.current) {
      recognitionRef.current.onend = null;
      try { recognitionRef.current.stop(); } catch(e) {}
      recognitionRef.current = null;
    }
    if (synthRef.current) {
      synthRef.current.cancel();
    }

    if (vapiRef.current) {
      vapiRef.current.stop();
      vapiRef.current = null;
    }

    setCallState('ended');

    // Trigger local backend call summary creation for simulated calls
    if (simulatedCallIdRef.current) {
      const durationSec = (Date.now() - callStartRef.current) / 1000;
      try {
        const res = await fetch(`${API_BASE}/api/v1/voice/webhook`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            message: {
              type: 'end-of-call-report',
              call: {
                id: simulatedCallIdRef.current,
                duration: durationSec
              }
            }
          })
        });
        if (res.ok) {
          const data = await res.json();
          setSummary(data.summary);
        }
      } catch (e) {
        console.error('Failed to trigger call summary:', e);
      }
      simulatedCallIdRef.current = '';
    }
  };

  const toggleMute = () => {
    const nextState = !isMuted;
    setIsMuted(nextState);
    if (vapiRef.current) {
      vapiRef.current.setMuted(nextState);
    }
    if (nextState) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch(e) {}
      }
      if (synthRef.current) {
        synthRef.current.cancel();
      }
    } else {
      if (recognitionRef.current && callState === 'active') {
        try { recognitionRef.current.start(); } catch(e) {}
      }
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl transition-all duration-300">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-950/40 px-6 py-4">
          <div className="flex items-center gap-2">
            <Phone className="h-5 w-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-100">Voice Assistant</h3>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Telephony Node</p>
            </div>
          </div>
          {callState === 'active' && (
            <div className="rounded-full bg-cyan-950/40 px-2.5 py-0.5 border border-cyan-800/30 text-[10px] text-cyan-400 font-semibold uppercase">
              Topic: {activeTopic}
            </div>
          )}
        </div>

        {/* Call Panel / Avatar */}
        <div className="flex flex-col items-center justify-center py-10 px-6 bg-slate-950/20">
          {callState !== 'ended' ? (
            <div className="relative flex h-28 w-28 items-center justify-center mb-6">
              {/* Animated pulsating circles */}
              {callState === 'active' && (
                <>
                  <div
                    className="absolute inset-0 rounded-full border border-cyan-500/20 animate-ping opacity-40"
                    style={{ transform: `scale(${pulseCount[0]})` }}
                  ></div>
                  <div
                    className="absolute -inset-4 rounded-full border border-cyan-500/10 animate-ping opacity-20"
                    style={{ transform: `scale(${pulseCount[1]})`, animationDelay: '200ms' }}
                  ></div>
                </>
              )}

              {/* Avatar Center Node */}
              <div
                className={`flex h-24 w-24 items-center justify-center rounded-full border shadow-xl transition-all duration-300 ${
                  callState === 'active'
                    ? 'border-cyan-500 bg-cyan-950/40 text-cyan-400 shadow-cyan-500/10'
                    : callState === 'connecting'
                    ? 'border-amber-500/50 bg-amber-950/20 text-amber-400 animate-pulse'
                    : 'border-slate-800 bg-slate-950 text-slate-500'
                }`}
              >
                <Phone className="h-8 w-8" />
              </div>
            </div>
          ) : null}

          {/* Call Status Description */}
          {callState === 'idle' && (
            <div className="text-center space-y-2">
              <p className="text-xs text-slate-400 px-6">
                Start a live voice call to discuss career experience, coding stack, or book an interview directly.
              </p>
              <button
                onClick={handleStartCall}
                className="flex items-center gap-2 rounded-xl bg-cyan-500 px-6 py-2.5 text-xs font-bold text-slate-950 hover:bg-cyan-400 transition"
              >
                <Phone className="h-4 w-4" />
                Start Voice Call
              </button>
            </div>
          )}

          {callState === 'connecting' && (
            <p className="text-xs text-amber-400 font-semibold animate-pulse uppercase tracking-wider">
              Connecting Call Agent...
            </p>
          )}

          {callState === 'active' && (
            <div className="w-full space-y-4">
              <VoiceTranscript history={transcript} />
              
              {/* Simulator Text Input Fallback */}
              {simulatedCallIdRef.current && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const form = e.currentTarget;
                    const inputEl = form.elements.namedItem('simulatedInput') as HTMLInputElement;
                    const text = inputEl.value;
                    if (text.trim()) {
                      handleUserUtterance(text.trim());
                      inputEl.value = '';
                    }
                  }}
                  className="flex gap-2 px-2"
                >
                  <input
                    name="simulatedInput"
                    type="text"
                    placeholder="Type to simulate spoken sentence..."
                    className="flex-1 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
                  />
                  <button
                    type="submit"
                    className="rounded-xl bg-cyan-600 px-4 py-2 text-xs font-bold text-slate-100 hover:bg-cyan-500 transition active:scale-95"
                  >
                    Simulate
                  </button>
                </form>
              )}

              {/* Call Controls */}
              <div className="flex items-center justify-center gap-4 pt-4 border-t border-slate-850">
                <button
                  onClick={toggleMute}
                  className={`rounded-full p-3 border transition active:scale-95 ${
                    isMuted
                      ? 'border-rose-500/50 bg-rose-950/20 text-rose-400'
                      : 'border-slate-850 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                  title={isMuted ? 'Unmute microphone' : 'Mute microphone'}
                >
                  {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
                </button>
                
                <button
                  onClick={handleEndCall}
                  className="rounded-full bg-rose-500 p-3.5 text-white hover:bg-rose-600 transition active:scale-95 shadow-lg shadow-rose-900/30"
                  title="Hang Up"
                >
                  <PhoneOff className="h-5 w-5" />
                </button>
              </div>
            </div>
          )}

          {callState === 'error' && (
            <div className="text-center space-y-3">
              <p className="text-xs text-rose-400">Connection error. Please try again.</p>
              <button
                onClick={handleStartCall}
                className="rounded-xl bg-slate-800 border border-slate-700 px-5 py-2 text-xs font-semibold hover:bg-slate-700 transition"
              >
                Retry Call
              </button>
            </div>
          )}

          {/* Call Summaries Panel (When Call Ends) */}
          {callState === 'ended' && summary && (
            <div className="w-full space-y-4">
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-emerald-900/30 pb-2">
                  <CheckCircle className="h-4.5 w-4.5 text-emerald-400" />
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                    Call Record Logged
                  </span>
                </div>
                
                {/* Details list */}
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> Call Duration:</span>
                    <strong className="text-slate-200">{summary.call_duration}</strong>
                  </div>
                  
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="flex items-center gap-1.5"><Award className="h-3.5 w-3.5" /> Booking Created:</span>
                    <strong className={summary.booking_created ? 'text-emerald-400' : 'text-slate-400'}>
                      {summary.booking_created ? 'Yes' : 'No'}
                    </strong>
                  </div>

                  {summary.booking_created && summary.booking_id && (
                    <div className="flex items-center justify-between text-slate-400">
                      <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> Booking ID:</span>
                      <strong className="text-cyan-400 font-mono select-all">{summary.booking_id}</strong>
                    </div>
                  )}
                  
                  {summary.cancellation_completed && (
                    <div className="flex items-center justify-between text-slate-400">
                      <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> Transaction:</span>
                      <strong className="text-rose-400">Booking Cancelled</strong>
                    </div>
                  )}

                  <div className="pt-2 border-t border-slate-800/40">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                      Topics Discussed:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.topics_discussed.map((topic) => (
                        <span key={topic} className="rounded bg-slate-800 px-2 py-0.5 text-[9px] text-slate-300 font-medium">
                          {topic}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setCallState('idle')}
                className="w-full rounded-xl bg-slate-800 border border-slate-700 py-2.5 text-xs font-semibold hover:bg-slate-700 transition"
              >
                Close Summary
              </button>
            </div>
          )}
        </div>

        {/* Footer Close Button */}
        {callState !== 'active' && (
          <div className="border-t border-slate-800 bg-slate-950/40 px-6 py-3 text-right">
            <button
              onClick={onClose}
              className="text-xs text-slate-500 hover:text-slate-300 font-semibold"
            >
              Close Portal
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// Add simple logging helper to prevent undefined logger calls
const logger = {
  info: (msg: string) => console.log(`[Voice Portal] ${msg}`)
};
