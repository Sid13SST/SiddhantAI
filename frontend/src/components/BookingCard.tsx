'use client';

import React, { useState } from 'react';
import { BookingContext, BookingSlot } from '../types';
import { Calendar, Clock, Mail, BookOpen, CheckCircle, RefreshCw, XCircle } from 'lucide-react';

interface BookingCardProps {
  context: BookingContext;
  onAction: (text: string) => void;
}

export default function BookingCard({ context, onAction }: BookingCardProps) {
  const [emailInput, setEmailInput] = useState('');
  const [topicInput, setTopicInput] = useState('');
  const [customTimezone, setCustomTimezone] = useState('');

  const { step, action, timezone, email, topic, available_slots } = context;

  if (step === 'none' || action === 'none') {
    return null;
  }

  // Group slots by date for premium visual structure
  const getGroupedSlots = (slots: BookingSlot[]) => {
    const groups: { [key: string]: BookingSlot[] } = {};
    slots.forEach((slot) => {
      // display is like "Tomorrow at 3:00 PM IST" or "Monday, June 8 at 2:30 PM IST"
      let dayKey = 'Available Date';
      if (slot.display.toLowerCase().includes('tomorrow')) {
        dayKey = 'Tomorrow';
      } else if (slot.display.toLowerCase().includes('today')) {
        dayKey = 'Today';
      } else {
        const parts = slot.display.split(' at ');
        if (parts.length > 0) {
          dayKey = parts[0];
        }
      }
      if (!groups[dayKey]) {
        groups[dayKey] = [];
      }
      groups[dayKey].push(slot);
    });
    return groups;
  };

  const handleTimezoneSelect = (tz: string) => {
    onAction(tz);
  };

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (emailInput.trim()) {
      onAction(emailInput.trim());
    }
  };

  const handleTopicSubmit = (topicStr: string) => {
    onAction(topicStr);
  };

  const handleSlotSelect = (index: number) => {
    onAction((index + 1).toString());
  };

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur-md transition-all duration-300 hover:border-slate-700 hover:shadow-lg hover:shadow-cyan-500/5">
      {/* Card Header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 bg-slate-950/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-cyan-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            {action === 'booking'
              ? 'Schedule Interview'
              : action === 'reschedule'
              ? 'Reschedule Interview'
              : 'Cancel Interview'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-cyan-950/30 px-2 py-0.5 border border-cyan-800/30">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-400"></span>
          <span className="text-[10px] text-cyan-400 font-medium">Interactive Session</span>
        </div>
      </div>

      {/* Card Content based on Step */}
      <div className="p-4">
        {step === 'ask_timezone' && (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">Select your timezone to show available slots:</p>
            <div className="grid grid-cols-3 gap-2">
              {['IST', 'EST', 'PST', 'GMT', 'UTC', 'SGT'].map((tz) => (
                <button
                  key={tz}
                  onClick={() => handleTimezoneSelect(tz)}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 py-2 text-xs font-medium text-slate-300 transition hover:border-cyan-500/50 hover:bg-cyan-950/20 hover:text-cyan-400 active:scale-95"
                >
                  {tz}
                </button>
              ))}
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (customTimezone.trim()) handleTimezoneSelect(customTimezone.trim());
              }}
              className="flex items-center gap-2 pt-1"
            >
              <input
                type="text"
                placeholder="Other (e.g. CET, JST)"
                value={customTimezone}
                onChange={(e) => setCustomTimezone(e.target.value)}
                className="flex-1 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-1.5 text-xs text-slate-300 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
              />
              <button
                type="submit"
                className="rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-cyan-400"
              >
                Apply
              </button>
            </form>
          </div>
        )}

        {step === 'ask_email' && (
          <form onSubmit={handleEmailSubmit} className="space-y-3">
            <p className="text-sm text-slate-300">Please provide your email for the calendar invitation:</p>
            <div className="relative">
              <Mail className="absolute top-2.5 left-3 h-4 w-4 text-slate-500" />
              <input
                type="email"
                required
                placeholder="recruiter@company.com"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                className="w-full rounded-lg border border-slate-800 bg-slate-950/40 py-2 pr-3 pl-9 text-xs text-slate-300 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/50"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-cyan-500 py-2 text-xs font-semibold text-slate-950 hover:bg-cyan-400 transition"
            >
              Next Step
            </button>
          </form>
        )}

        {step === 'ask_topic' && (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">Choose or type a topic for the interview:</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                'AI Engineering Role',
                'Backend Engineer Role',
                'General Coding Chat',
                'Project Walkthrough',
              ].map((topicOption) => (
                <button
                  key={topicOption}
                  onClick={() => handleTopicSubmit(topicOption)}
                  className="rounded-lg border border-slate-800 bg-slate-950/40 p-2 text-left text-xs text-slate-300 transition hover:border-cyan-500/50 hover:bg-cyan-950/20 hover:text-cyan-400"
                >
                  {topicOption}
                </button>
              ))}
            </div>
            <div className="flex gap-2 pt-1">
              <input
                type="text"
                placeholder="Custom topic..."
                value={topicInput}
                onChange={(e) => setTopicInput(e.target.value)}
                className="flex-1 rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-1.5 text-xs text-slate-300 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none"
              />
              <button
                onClick={() => topicInput.trim() && handleTopicSubmit(topicInput.trim())}
                className="rounded-lg bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-cyan-400"
              >
                Send
              </button>
            </div>
          </div>
        )}

        {(step === 'recommend_slots' || step === 'reschedule_recommend_slots') && available_slots && (
          <div className="space-y-3">
            <p className="text-sm text-slate-300 flex items-center gap-1">
              <Clock className="h-4 w-4 text-cyan-400" />
              <span>Select an available timeslot ({timezone || 'IST'}):</span>
            </p>
            <div className="space-y-3">
              {Object.entries(getGroupedSlots(available_slots)).map(([day, slots]) => (
                <div key={day} className="space-y-1">
                  <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{day}</div>
                  <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                    {slots.map((slot) => {
                      const idx = available_slots.findIndex((s) => s.utc === slot.utc);
                      // Extract time component (e.g. 3:00 PM IST)
                      const timeStr = slot.display.split(' at ')[1] || slot.display;
                      return (
                        <button
                          key={slot.utc}
                          onClick={() => handleSlotSelect(idx)}
                          className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-left text-xs text-slate-300 transition hover:border-cyan-500/50 hover:bg-cyan-950/20 hover:text-cyan-400"
                        >
                          <span className="font-medium">{timeStr}</span>
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] text-slate-400">
                            Slot {idx + 1}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {step === 'ask_cancellation_email' && (
          <form onSubmit={handleEmailSubmit} className="space-y-3">
            <p className="text-sm text-slate-300">Enter your email address to cancel the interview:</p>
            <div className="relative">
              <Mail className="absolute top-2.5 left-3 h-4 w-4 text-slate-500" />
              <input
                type="email"
                required
                placeholder="recruiter@company.com"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                className="w-full rounded-lg border border-slate-800 bg-slate-950/40 py-2 pr-3 pl-9 text-xs text-slate-300 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-rose-500/20 border border-rose-500/30 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-500 hover:text-white transition"
            >
              Cancel Booking
            </button>
          </form>
        )}

        {step === 'ask_reschedule_email' && (
          <form onSubmit={handleEmailSubmit} className="space-y-3">
            <p className="text-sm text-slate-300">Enter your email address to find and reschedule your interview:</p>
            <div className="relative">
              <Mail className="absolute top-2.5 left-3 h-4 w-4 text-slate-500" />
              <input
                type="email"
                required
                placeholder="recruiter@company.com"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                className="w-full rounded-lg border border-slate-800 bg-slate-950/40 py-2 pr-3 pl-9 text-xs text-slate-300 placeholder-slate-500"
              />
            </div>
            <button
              type="submit"
              className="w-full rounded-lg bg-amber-500/20 border border-amber-500/30 py-2 text-xs font-semibold text-amber-400 hover:bg-amber-500 hover:text-white transition"
            >
              Find Booking
            </button>
          </form>
        )}
      </div>

      {/* Progress Footer */}
      <div className="flex items-center justify-between border-t border-slate-800/80 bg-slate-950/20 px-4 py-2 text-[10px] text-slate-500">
        <div>
          {timezone && (
            <span>
              Timezone: <strong className="text-slate-400">{timezone}</strong>
            </span>
          )}
          {email && (
            <span className="ml-3">
              Email: <strong className="text-slate-400">{email}</strong>
            </span>
          )}
        </div>
        <button
          onClick={() => onAction('cancel')}
          className="text-slate-500 hover:text-rose-400 transition"
        >
          Cancel Flow
        </button>
      </div>
    </div>
  );
}
