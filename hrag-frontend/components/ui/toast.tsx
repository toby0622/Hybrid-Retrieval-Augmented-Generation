"use client";

import { CheckCircle2, Info, X, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Toast } from '@/types';

interface ToastNotificationProps {
  toasts: Toast[];
  removeToast: (id: number) => void;
}

export function ToastNotification({ toasts, removeToast }: ToastNotificationProps) {
  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map(toast => (
        <div 
          key={toast.id} 
          className={cn(
            "pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg shadow-xl border animate-in slide-in-from-right-10 fade-in duration-300",
            toast.type === 'success' && 'bg-emerald-900/90 text-emerald-100 border-emerald-700',
            toast.type === 'info' && 'bg-blue-900/90 text-blue-100 border-blue-700',
            toast.type === 'error' && 'bg-red-900/90 text-red-100 border-red-700'
          )}
        >
          {toast.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
          {toast.type === 'info' && <Info className="w-5 h-5 text-blue-400" />}
          {toast.type === 'error' && <AlertCircle className="w-5 h-5 text-red-400" />}
          <div className="flex-1 text-sm font-medium">{toast.message}</div>
          <button 
            onClick={() => removeToast(toast.id)} 
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
