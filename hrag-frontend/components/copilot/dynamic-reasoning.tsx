"use client";

import { useState, useEffect } from 'react';
import { Activity, CheckCircle2, Loader2 } from 'lucide-react';
import { ReasoningStep } from '@/types';

interface DynamicReasoningProps {
  steps: ReasoningStep[];
  isStreaming?: boolean;
}

export function DynamicReasoning({ steps, isStreaming = false }: DynamicReasoningProps) {
  const [displayedSteps, setDisplayedSteps] = useState<ReasoningStep[]>([]);
  
  useEffect(() => {
    if (isStreaming) {
      setDisplayedSteps(steps);
    } else {
      setDisplayedSteps([]);
      steps.forEach((step, index) => {
        setTimeout(() => {
          setDisplayedSteps(prev => [...prev, { ...step, status: 'completed' }]);
        }, index * 600);
      });
    }
  }, [steps, isStreaming]);

  const allStepsCompleted = displayedSteps.length > 0 && 
    displayedSteps.every(s => s.status === 'completed');

  return (
    <div className="bg-slate-900 rounded-lg p-4 border border-slate-800 w-fit shadow-inner">
      <div className="flex items-center gap-2 text-xs font-semibold text-blue-400 mb-3 uppercase tracking-wider">
        <Activity className="w-3 h-3 animate-pulse" /> REASONING PROCESS
      </div>
      <div className="space-y-2">
        {displayedSteps.map((step) => {
          const isActive = step.status === 'active';
          const isCompleted = step.status === 'completed';
          const isPending = !isActive && !isCompleted;
          
          return (
            <div 
              key={step.id} 
              className="flex items-center gap-3 text-sm py-1 animate-in slide-in-from-left-2 duration-300"
            >
              {isCompleted ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              ) : isActive ? (
                <div className="w-4 h-4 flex items-center justify-center">
                  <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                <div className="w-4 h-4 flex items-center justify-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-700" />
                </div>
              )}
              
              <span className={
                isCompleted ? 'text-slate-400' : 
                isActive ? 'text-blue-200 font-medium' : 
                'text-slate-600'
              }>
                {step.label}
              </span>
            </div>
          );
        })}
        
        {isStreaming && allStepsCompleted && (
          <div className="flex items-center gap-3 text-sm py-2 mt-2 pt-2 border-t border-slate-800">
            <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
            <span className="text-amber-300 font-medium">
              Generating diagnostic response...
            </span>
          </div>
        )}
        
        {isStreaming && !allStepsCompleted && (
          <div className="flex items-center gap-3 text-sm py-1 opacity-50 pl-0.5">
            <div className="w-3 h-3 rounded-full bg-slate-800 border border-slate-700" />
            <span className="text-slate-600 text-xs">Processing...</span>
          </div>
        )}
      </div>
    </div>
  );
}
