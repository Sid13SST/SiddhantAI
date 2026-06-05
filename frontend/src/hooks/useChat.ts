'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Message, BookingContext, Citation } from '../types';
import { API_BASE } from '../services/api';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [currentBookingContext, setCurrentBookingContext] = useState<BookingContext>({
    step: 'none',
    action: 'none',
  });
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [evidenceOpen, setEvidenceOpen] = useState<boolean>(false);
  const [activeEvidence, setActiveEvidence] = useState<Citation[]>([]);
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentTopic, setCurrentTopic] = useState<string>('General QA');

  // Initialize session ID from localStorage on mount
  useEffect(() => {
    const cached = localStorage.getItem('siddhant_ai_session');
    if (cached) {
      setSessionId(cached);
      // Fetch initial session context from backend if any
      fetch(`${API_BASE}/api/v1/booking/availability?duration_minutes=30`)
        .then(() => {})
        .catch(() => {});
    } else {
      const newId = `sess_${Math.random().toString(36).substring(2, 15)}`;
      setSessionId(newId);
      localStorage.setItem('siddhant_ai_session', newId);
    }
  }, []);

  // Sync Current Topic based on active booking flow or conversation context
  useEffect(() => {
    if (currentBookingContext.action === 'booking') {
      setCurrentTopic('Scheduling Interview');
    } else if (currentBookingContext.action === 'reschedule') {
      setCurrentTopic('Interview Rescheduling');
    } else if (currentBookingContext.action === 'cancellation') {
      setCurrentTopic('Interview Cancellation');
    } else {
      // Look at the last assistant message content to infer topic if any
      const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
      if (lastAssistant) {
        if (lastAssistant.content.toLowerCase().includes('gradonix')) {
          setCurrentTopic('Gradonix Context');
        } else if (
          lastAssistant.content.toLowerCase().includes('tech') ||
          lastAssistant.content.toLowerCase().includes('technologies')
        ) {
          setCurrentTopic('Technical Stack');
        } else if (
          lastAssistant.content.toLowerCase().includes('hire') ||
          lastAssistant.content.toLowerCase().includes('recruit')
        ) {
          setCurrentTopic('Hiring Alignment');
        } else {
          setCurrentTopic('General QA');
        }
      } else {
        setCurrentTopic('General QA');
      }
    }
  }, [currentBookingContext, messages]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setCurrentBookingContext({ step: 'none', action: 'none' });
    setActiveEvidence([]);
    setSelectedCitationIndex(null);
    setEvidenceOpen(false);
    setError(null);
    setCurrentTopic('General QA');
    const newId = `sess_${Math.random().toString(36).substring(2, 15)}`;
    setSessionId(newId);
    localStorage.setItem('siddhant_ai_session', newId);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isTyping) return;

      setError(null);
      const userMsg: Message = {
        id: `msg_${Date.now()}_user`,
        role: 'user',
        content: text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsTyping(true);

      const assistantMsgId = `msg_${Date.now()}_assistant`;
      const assistantMsgPlaceholder: Message = {
        id: assistantMsgId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        loading: true,
      };

      setMessages((prev) => [...prev, assistantMsgPlaceholder]);

      try {
        const response = await fetch(`${API_BASE}/ask/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question: text,
            session_id: sessionId,
            booking_context: currentBookingContext,
          }),
        });

        if (!response.ok) {
          throw new Error(`Server returned error: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response stream reader not available');
        }

        const decoder = new TextDecoder();
        let buffer = '';
        let streamedAnswer = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const jsonStr = trimmed.slice(6);
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);
              if (data.type === 'token') {
                streamedAnswer += data.content;
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? { ...msg, content: streamedAnswer, loading: false }
                      : msg
                  )
                );
              } else if (data.type === 'metadata') {
                // Compile typed citations list
                const formattedCitations: Citation[] = (data.citations || []).map(
                  (c: any, index: number) => {
                    // Check if citation is simple string or object
                    if (typeof c === 'string') {
                      return {
                        index: index + 1,
                        text: `[${index + 1}]`,
                        source: data.sources?.[index]?.source || 'Source Document',
                        snippet: data.sources?.[index]?.snippet || c,
                      };
                    }
                    return {
                      index: index + 1,
                      text: c.text || `[${index + 1}]`,
                      source: c.source || 'Source Document',
                      snippet: c.snippet || '',
                    };
                  }
                );

                // Compile source list for badges
                const sourcesList: string[] = [];
                if (data.sources) {
                  data.sources.forEach((src: any) => {
                    const srcName = (src.source || '').toLowerCase();
                    if (srcName.includes('resume')) {
                      if (!sourcesList.includes('Resume')) sourcesList.push('Resume');
                    } else if (srcName.includes('readme') || srcName.includes('repo')) {
                      if (!sourcesList.includes('README')) sourcesList.push('README');
                    } else if (srcName.includes('commit') || srcName.includes('git commit')) {
                      if (!sourcesList.includes('Commit')) sourcesList.push('Commit');
                    } else if (
                      srcName.includes('code') ||
                      srcName.includes('.py') ||
                      srcName.includes('.js') ||
                      srcName.includes('.ts') ||
                      srcName.includes('source code')
                    ) {
                      if (!sourcesList.includes('Code')) sourcesList.push('Code');
                    }
                  });
                }
                // Fallback badges if none matched but sources are present
                if (sourcesList.length === 0 && data.sources && data.sources.length > 0) {
                  sourcesList.push('Code');
                }

                // If booking context changes, update it
                const nextBookingContext = data.booking_context || { step: 'none', action: 'none' };
                setCurrentBookingContext(nextBookingContext);

                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? {
                          ...msg,
                          content: data.answer || streamedAnswer,
                          citations: formattedCitations,
                          sources: sourcesList,
                          confidence: data.confidence,
                          bookingContext: nextBookingContext,
                          loading: false,
                        }
                      : msg
                  )
                );

                // Update evidence panel dataset if citations exist
                if (formattedCitations.length > 0) {
                  setActiveEvidence(formattedCitations);
                }
              }
            } catch (e) {
              console.error('Error parsing stream chunk JSON:', e, jsonStr);
            }
          }
        }
      } catch (err: any) {
        console.error('Error streaming chat message:', err);
        setError(err.message || 'Network error connecting to AI representative.');
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: 'Error: Failed to fetch response. Make sure the backend API server is running.',
                  loading: false,
                }
              : msg
          )
        );
      } finally {
        setIsTyping(false);
      }
    },
    [sessionId, currentBookingContext, isTyping]
  );

  return {
    messages,
    isTyping,
    currentTopic,
    currentBookingContext,
    evidenceOpen,
    setEvidenceOpen,
    activeEvidence,
    setActiveEvidence,
    selectedCitationIndex,
    setSelectedCitationIndex,
    error,
    sendMessage,
    clearChat,
  };
}
export type UseChatReturn = ReturnType<typeof useChat>;
