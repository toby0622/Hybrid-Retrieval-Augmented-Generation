"use client";

import { useState } from 'react';
import { Sidebar } from '@/components/layout/sidebar';
import { ChatInterface } from '@/components/copilot/chat-interface';
import { KnowledgeInterface } from '@/components/knowledge/knowledge-interface';
import { ToastNotification } from '@/components/ui/toast';
import { useToast } from '@/hooks/use-toast';
import { TabType } from '@/types';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('copilot');
  const { toasts, addToast, removeToast } = useToast();

  return (
    <div className="flex w-full h-screen bg-black text-slate-200 font-sans selection:bg-blue-500/30">
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      {/* Toast Container */}
      <ToastNotification toasts={toasts} removeToast={removeToast} />

      <main className="flex-1 overflow-hidden relative">
        {/* Background Pattern */}
        <div 
          className="absolute inset-0 pointer-events-none opacity-10" 
          style={{ 
            backgroundImage: 'radial-gradient(#4b5563 1px, transparent 1px)', 
            backgroundSize: '20px 20px' 
          }} 
        />
        
        {activeTab === 'copilot' ? (
          <ChatInterface addToast={addToast} />
        ) : (
          <KnowledgeInterface addToast={addToast} />
        )}
      </main>
    </div>
  );
}
