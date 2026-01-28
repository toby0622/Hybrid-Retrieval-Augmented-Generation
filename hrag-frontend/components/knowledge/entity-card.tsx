"use client";

import { GitMerge, Search, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { GardenerTask } from '@/types';

interface EntityCardProps {
  task: GardenerTask;
  onResolve: (id: number, action: 'approve' | 'reject') => void;
}

export function EntityCard({ task, onResolve }: EntityCardProps) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex flex-col gap-4 hover:border-slate-600 transition-all hover:shadow-lg hover:shadow-black/20 w-full animate-in slide-in-from-bottom-2 duration-300">
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded ${task.type === 'conflict' ? 'bg-amber-500/20 text-amber-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
            {task.type === 'conflict' ? <GitMerge className="w-4 h-4" /> : <Search className="w-4 h-4" />}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-200">{task.entityName}</div>
            <div className="text-xs text-slate-500 flex items-center gap-1">
              Source: {task.source} • <span className="text-blue-400">{(task.confidence * 100).toFixed(0)}% Similarity</span>
            </div>
          </div>
        </div>
        <div className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-[10px] text-slate-400 uppercase tracking-wide">
          Pending
        </div>
      </div>

      {task.type === 'conflict' && task.existingEntity && task.newEntity && (
        <div className="grid grid-cols-2 gap-4 bg-slate-900/50 rounded p-3 text-xs border border-slate-700/50">
          <div>
            <div className="text-slate-500 mb-1">Existing in Graph</div>
            <div className="font-semibold text-slate-300">{task.existingEntity.name}</div>
            <div className="text-slate-400 mt-1 line-clamp-2">{task.existingEntity.desc}</div>
          </div>
          <div className="border-l border-slate-700 pl-4">
            <div className="text-slate-500 mb-1">Extracted from New Doc</div>
            <div className="font-semibold text-slate-300">{task.newEntity.name}</div>
            <div className="text-emerald-400/80 mt-1 line-clamp-2">{task.newEntity.desc}</div>
          </div>
        </div>
      )}

      {task.type === 'new' && task.desc && (
        <div className="text-xs text-slate-400 bg-slate-900/50 p-3 rounded border border-slate-700/50">
          {task.desc}
        </div>
      )}

      <div className="flex gap-2 mt-auto pt-2">
        <Button 
          variant="outline"
          size="sm"
          onClick={() => onResolve(task.id, 'reject')}
          className="flex-1"
        >
          Reject / Edit
        </Button>
        <Button 
          variant="success"
          size="sm"
          onClick={() => onResolve(task.id, 'approve')}
          className="flex-1"
        >
          <CheckCircle2 className="w-3 h-3" />
          {task.type === 'conflict' ? 'Merge & Update' : 'Approve Entity'}
        </Button>
      </div>
    </div>
  );
}
