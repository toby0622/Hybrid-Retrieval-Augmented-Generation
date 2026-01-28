"use client";

import React from 'react';
import { MessageSquare, Database, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';
import { TabType } from '@/types';

interface SidebarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
}

interface NavButtonProps {
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
  label: string;
}

function NavButton({ icon, active, onClick, label }: NavButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "p-3 rounded-lg w-full flex justify-center transition-all duration-200 group relative",
        active 
          ? "bg-slate-800 text-blue-400 border border-slate-700 shadow-sm" 
          : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
      )}
    >
      {icon}
      <span className="absolute left-16 bg-slate-800 text-slate-200 text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap border border-slate-700 pointer-events-none z-50">
        {label}
      </span>
    </button>
  );
}

export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  return (
    <div className="w-20 bg-slate-900 border-r border-slate-700 flex flex-col items-center py-6 gap-6 z-20">
      {/* Logo */}
      <div className="p-3 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/30">
        <Cpu className="text-white w-6 h-6" />
      </div>
      
      {/* Navigation */}
      <div className="flex-1 flex flex-col gap-4 w-full px-2">
        <NavButton 
          icon={<MessageSquare size={24} />} 
          active={activeTab === 'copilot'} 
          onClick={() => setActiveTab('copilot')} 
          label="Copilot"
        />
        <NavButton 
          icon={<Database size={24} />} 
          active={activeTab === 'knowledge'} 
          onClick={() => setActiveTab('knowledge')} 
          label="Knowledge"
        />
      </div>
      
      {/* User Avatar */}
      <div className="mt-auto mb-4">
        <div className="w-10 h-10 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 border border-slate-600">
          DEV
        </div>
      </div>
    </div>
  );
}
