"use client";

import { useState } from 'react';
import { 
  ChevronDown, 
  Workflow, 
  Terminal, 
  Search, 
  XCircle, 
  AlertTriangle,
  Zap,
  ArrowDown,
  GitMerge,
  CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { DiagnosticStep, DiagnosticResponse } from '@/types';

interface DiagnosticNodeProps {
  step: DiagnosticStep;
  isRoot?: boolean;
  onClick: (id: string) => void;
  isExpanded: boolean;
}

function DiagnosticNode({ step, isRoot = false, onClick, isExpanded }: DiagnosticNodeProps) {
  const getStatusColor = () => {
    if (step.status === 'error') return { border: 'border-red-500', bg: 'bg-red-500/10', text: 'text-red-400', icon: 'text-red-500' };
    if (step.status === 'warning') return { border: 'border-amber-500', bg: 'bg-amber-500/10', text: 'text-amber-400', icon: 'text-amber-500' };
    return { border: 'border-blue-500', bg: 'bg-blue-500/10', text: 'text-blue-400', icon: 'text-blue-500' };
  };

  const style = getStatusColor();
  const StatusIcon = step.status === 'error' ? XCircle : step.status === 'warning' ? AlertTriangle : Search;

  return (
    <div 
      className={cn(
        "relative group cursor-pointer transition-all duration-300",
        isRoot ? 'w-full' : 'flex-1 min-w-[200px]'
      )}
      onClick={() => onClick(step.id)}
    >
      <div 
        className={cn(
          "rounded-lg border backdrop-blur-sm overflow-hidden transition-all duration-300",
          isExpanded 
            ? "border-blue-500/50 bg-slate-800 ring-1 ring-blue-500/20 shadow-lg"
            : "border-slate-700/60 bg-slate-900/60 hover:bg-slate-800 hover:border-slate-600"
        )}
      >
        <div className="p-3.5 flex items-start gap-3">
          <div className={cn("mt-0.5 w-8 h-8 rounded flex items-center justify-center shrink-0 border", style.border, style.bg)}>
            {isRoot ? <Zap className={cn("w-4 h-4", style.icon)} /> : <StatusIcon className={cn("w-4 h-4", style.icon)} />}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-1">
              <span className={cn("text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-slate-950/50 border border-slate-800", style.text)}>
                {step.source}
              </span>
              <ChevronDown className={cn("w-3.5 h-3.5 text-slate-500 transition-transform duration-300", isExpanded && "rotate-180 text-blue-400")} />
            </div>
            
            <div className={cn("text-sm font-medium truncate", isExpanded ? 'text-blue-100' : 'text-slate-200')}>
              {step.title}
            </div>
            
            {!isExpanded && (
              <div className="text-xs text-slate-500 truncate mt-1 opacity-80">{step.detail}</div>
            )}
          </div>
        </div>

        {isExpanded && (
          <div className="border-t border-slate-700/50 bg-slate-950/30 p-3 animate-in slide-in-from-top-2 duration-200">
            <div className="text-xs text-slate-300 mb-3 leading-relaxed">
              {step.detail}
            </div>
             
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
                <Terminal className="w-3 h-3" /> Raw Evidence
              </div>
              <div className="font-mono text-[10px] leading-relaxed bg-black/60 p-2.5 rounded border border-slate-800/60 text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-48 scrollbar-thin scrollbar-thumb-slate-700">
                {typeof step.raw_content?.data === 'object' 
                  ? JSON.stringify(step.raw_content.data, null, 2) 
                  : String(step.raw_content?.data || '')}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface DiagnosticCardProps {
  diagnostic: DiagnosticResponse;
  onAction: (action: 'case_study' | 'resolve') => void;
}

export function DiagnosticCard({ diagnostic, onAction }: DiagnosticCardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  
  const rootNode = diagnostic.path.find(p => p.is_root);
  const leafNodes = diagnostic.path.filter(p => p.is_parallel);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="bg-slate-900/30 rounded-xl border border-slate-700/50 p-1 mt-2 max-w-5xl overflow-hidden animate-in fade-in duration-500 hover:border-slate-600/50 transition-colors">
      
      <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800/50 bg-slate-900/20">
        <div className="p-1 rounded bg-indigo-500/10">
          <Workflow className="w-4 h-4 text-indigo-400" />
        </div>
        <span className="font-semibold text-slate-200 text-sm">Diagnostic Path Analysis</span>
      </div>
      
      <div className="p-4 flex flex-col gap-4">
        
        {rootNode && (
          <div className="relative z-20">
            <DiagnosticNode 
              step={rootNode} 
              isRoot={true} 
              onClick={toggleExpand} 
              isExpanded={expandedId === rootNode.id} 
            />
          </div>
        )}

        {leafNodes.length > 0 && (
          <div className="flex items-center justify-center -my-2 relative z-10 opacity-60">
            <div className="flex flex-col items-center">
              <div className="h-4 w-px bg-gradient-to-b from-slate-600 to-slate-800"></div>
              <div className="bg-slate-800 border border-slate-700 rounded-full px-2 py-0.5 flex items-center gap-1 shadow-sm">
                <span className="text-[10px] text-slate-400 font-medium">Correlated Events</span>
                <ArrowDown className="w-3 h-3 text-slate-500" />
              </div>
              <div className="h-4 w-px bg-gradient-to-b from-slate-800 to-transparent"></div>
            </div>
          </div>
        )}

        {leafNodes.length > 0 && (
          <div className="bg-slate-800/20 rounded-xl border border-slate-800/50 p-3 pt-4">
            <div className="flex w-full gap-3 sm:gap-4 justify-center items-start flex-wrap">
              {leafNodes.map((node) => (
                <DiagnosticNode 
                  key={node.id}
                  step={node} 
                  onClick={toggleExpand} 
                  isExpanded={expandedId === node.id} 
                />
              ))}
            </div>
          </div>
        )}

        <div className="mt-2 bg-gradient-to-r from-indigo-950/40 to-slate-900/40 border border-indigo-500/20 rounded-lg p-4 flex gap-4 shadow-sm relative overflow-hidden">
          <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-500/60" />
          <div className="mt-0.5">
            <Terminal className="w-5 h-5 text-indigo-400" />
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold text-indigo-200 mb-1.5 flex items-center gap-2">
              Recommended Action
              <span className="text-[9px] uppercase tracking-wider font-semibold text-indigo-300 bg-indigo-500/10 px-1.5 py-0.5 rounded border border-indigo-500/20">
                {diagnostic.confidence > 0.8 ? 'High Confidence' : 'Medium Confidence'}
              </span>
            </div>
            <div className="text-sm text-slate-300 leading-relaxed opacity-90">
              {diagnostic.suggestion}
            </div>
          </div>
        </div>
        
        <div className="flex gap-2 justify-end pt-1">
          <Button 
            variant="outline"
            size="sm"
            onClick={() => onAction('case_study')}
          >
            <GitMerge className="w-3.5 h-3.5" /> Convert to Case Study
          </Button>
          <Button 
            variant="success"
            size="sm"
            onClick={() => onAction('resolve')}
          >
            <CheckCircle2 className="w-3.5 h-3.5" /> Issue Resolved
          </Button>
        </div>
      </div>
    </div>
  );
}
