"use client";

import { useState, useEffect } from 'react';
import { Activity, CheckCircle2 } from 'lucide-react';
import { ReasoningStep } from '@/types';

interface DynamicReasoningProps {
  steps: ReasoningStep[];
}

export function DynamicReasoning({ steps }: DynamicReasoningProps) {
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  
  useEffect(() => {
    if (currentStepIndex < steps.length) {
      const timer = setTimeout(() => {
        setCurrentStepIndex(prev => prev + 1);
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [currentStepIndex, steps.length]);

  const visibleSteps = steps.slice(0, currentStepIndex + 1);
  const isAllDone = currentStepIndex >= steps.length;

  return (
    <div className="bg-slate-900 rounded-lg p-4 border border-slate-800 w-full shadow-inner">
      <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 mb-3 uppercase tracking-wider">
        <Activity className="w-3 h-3 animate-pulse" /> REASONING PROCESS
      </div>
      <div className="space-y-2">
        {visibleSteps.map((step, i) => {
          const isStepDone = i < currentStepIndex; 
          return (
            <div 
              key={step.id} 
              className="flex items-center gap-3 text-sm py-1 animate-in slide-in-from-left-2 duration-300"
            >
              {isStepDone ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : (
                <div className="w-4 h-4 flex items-center justify-center">
                  <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
              <span className={isStepDone ? 'text-slate-400' : 'text-slate-200 font-medium'}>
                {step.label}
              </span>
            </div>
          );
        })}
        {!isAllDone && currentStepIndex < steps.length && (
           <div className="flex items-center gap-3 text-sm py-1 opacity-50 pl-0.5">
             <div className="w-3 h-3 rounded-full bg-slate-800 border border-slate-700" />
             <span className="text-slate-600 text-xs">Thinking...</span>
           </div>
        )}
      </div>
    </div>
  );
}
