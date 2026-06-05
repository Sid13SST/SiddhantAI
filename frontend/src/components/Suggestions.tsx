import React from 'react';
import { HelpCircle, Cpu, Award, Calendar } from 'lucide-react';

interface SuggestionsProps {
  onSelect: (text: string) => void;
}

export default function Suggestions({ onSelect }: SuggestionsProps) {
  const options = [
    {
      text: 'Tell me about Gradonix',
      icon: HelpCircle,
      desc: 'Understand the multi-agent calendar tool',
      color: 'hover:border-cyan-500/50 hover:bg-cyan-950/10 hover:text-cyan-400',
    },
    {
      text: 'What technologies does Siddhant use?',
      icon: Cpu,
      desc: 'Explore coding stack and expertise',
      color: 'hover:border-teal-500/50 hover:bg-teal-950/10 hover:text-teal-400',
    },
    {
      text: 'Why should we hire Siddhant?',
      icon: Award,
      desc: 'See technical strengths and credentials',
      color: 'hover:border-amber-500/50 hover:bg-amber-950/10 hover:text-amber-400',
    },
    {
      text: 'Book an interview',
      icon: Calendar,
      desc: 'Schedule a time directly on Google Calendar',
      color: 'hover:border-blue-500/50 hover:bg-blue-950/10 hover:text-blue-400',
    },
  ];

  return (
    <div className="w-full space-y-3">
      <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 block text-center">
        Quick Actions & Suggested Prompts
      </span>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {options.map((opt) => {
          const Icon = opt.icon;
          return (
            <button
              key={opt.text}
              onClick={() => onSelect(opt.text)}
              className={`flex flex-col items-start rounded-xl border border-slate-800 bg-slate-900/40 p-4.5 text-left transition duration-300 backdrop-blur-sm group hover:shadow-md ${opt.color}`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon className="h-4 w-4 text-slate-400 group-hover:scale-110 transition duration-300" />
                <span className="text-xs font-bold">{opt.text}</span>
              </div>
              <span className="text-[10px] text-slate-400 leading-normal">{opt.desc}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
