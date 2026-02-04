"use client";

import { useState, useRef, useEffect, useCallback } from 'react';
import { Cpu, Database, ChevronRight, Loader2, AlertCircle } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DynamicReasoning } from './dynamic-reasoning';
import { DiagnosticCard } from './diagnostic-card';
import { Message, ReasoningStep } from '@/types';
import { apiClient, StreamEvent } from '@/lib/api';

const INITIAL_MESSAGES: Message[] = [
  {
    id: 1,
    role: 'system',
    content: 'DevOps Copilot Online. Connecting to backend services...',
    timestamp: ''
  }
];

interface ChatInterfaceProps {
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function ChatInterface({ addToast }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [healthInfo, setHealthInfo] = useState<{neo4j: string, qdrant: string} | null>(null);
  const [modelName, setModelName] = useState<string>('Loading...');
  
  const [streamingSteps, setStreamingSteps] = useState<ReasoningStep[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingSteps]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await apiClient.health();
        const isHealthy = health.status === 'healthy' || health.status === 'degraded';
        setIsConnected(isHealthy);
        setHealthInfo({ neo4j: health.neo4j, qdrant: health.qdrant });
        setModelName(health.model_name || 'Unknown');
        setMessages([{
          id: 1,
          role: 'system',
          content: `DevOps Copilot Online. Neo4j: ${health.neo4j} | Qdrant: ${health.qdrant}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      } catch (error) {
        setIsConnected(false);
        setMessages([{
          id: 1,
          role: 'system',
          content: 'Backend connection failed. Please ensure the API server is running on localhost:8000',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
      }
    };
    checkHealth();
  }, []);

  const handleDiagnosticAction = async (actionType: 'case_study' | 'resolve') => {
    if (!threadId) return;

    if (actionType === 'case_study') {
      try {
        await apiClient.chat({
          query: 'Generate case study',
          thread_id: threadId,
          feedback: 'generate_case_study'
        });
        addToast('Requesting case study generation...', 'info');
      } catch (error) {
        console.error('Case study generation error:', error);
        addToast('Failed to trigger case study generation', 'error');
      }
    } else if (actionType === 'resolve') {
      try {
        await apiClient.chat({
          query: 'Issue resolved',
          thread_id: threadId,
          feedback: 'resolved'
        });
        addToast('Incident marked resolved. Feedback loop updated.', 'success');
      } catch (error) {
        console.error('Feedback error:', error);
        addToast('Failed to resolve incident', 'error');
      }
    }
  };

  const handleSendMessage = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now(),
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, userMsg]);
    const currentInput = input;
    setInput('');
    setIsLoading(true);
    setIsStreaming(true);
    setStreamingSteps([]);

    const handleStep = (step: ReasoningStep) => {
      setStreamingSteps(prev => {
        const existing = prev.find(s => s.id === step.id);
        if (existing) {
          return prev.map(s => s.id === step.id ? step : s);
        }
        return [...prev, step];
      });
    };

    const handleComplete = (event: StreamEvent) => {
      setIsStreaming(false);
      setStreamingSteps([]);
      
      if (event.thread_id) {
        setThreadId(event.thread_id);
      }

      if (event.diagnostic) {
        const diagnosticMsg: Message = {
          id: Date.now() + 1,
          role: 'assistant',
          type: 'diagnostic',
          content: event.response || '',
          diagnostic: event.diagnostic,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, diagnosticMsg]);
      } else if (event.clarification_question) {
        const clarificationMsg: Message = {
          id: Date.now() + 1,
          role: 'assistant',
          content: event.clarification_question,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else {
        const textMsg: Message = {
          id: Date.now() + 1,
          role: 'assistant',
          content: event.response || 'No response received.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, textMsg]);
      }
      
      setIsLoading(false);
    };

    const handleError = (error: string) => {
      setIsStreaming(false);
      setStreamingSteps([]);
      
      const errorMsg: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: `Connection error: ${error}. Please check if the backend is running.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
      addToast('Failed to connect to backend API', 'error');
      setIsLoading(false);
    };

    await apiClient.chatStream(
      { query: currentInput, thread_id: threadId || undefined },
      handleStep,
      handleComplete,
      handleError
    );
  }, [input, isLoading, threadId, addToast]);

  return (
    <div className="flex flex-col h-full bg-slate-950 relative overflow-hidden">
      <div className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-950/80 backdrop-blur-sm z-10 sticky top-0">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            iDoctor Copilot
            {isConnected === null ? (
              <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
                <Loader2 className="w-3 h-3 inline animate-spin mr-1" /> Connecting...
              </span>
            ) : isConnected ? (
              <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Connected
              </span>
            ) : (
              <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                <AlertCircle className="w-3 h-3 inline mr-1" /> Disconnected
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-500">Retrieval: Hybrid (Graph + Vector) • Model: {modelName}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-lg ${
              msg.role === 'user' ? 'bg-indigo-600 shadow-indigo-500/20' : 'bg-blue-600 shadow-blue-500/20'
            }`}>
              {msg.role === 'user' ? <div className="text-xs font-bold text-white">U</div> : <Cpu className="w-4 h-4 text-white" />}
            </div>

            <div className={`max-w-[90%] lg:max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'} flex flex-col`}>
              <div className="flex items-center gap-2 mb-1 opacity-70">
                <span className="text-xs font-bold text-slate-300">
                  {msg.role === 'user' ? 'You' : msg.role === 'system' ? 'System' : 'DevOps Copilot'}
                </span>
                <span className="text-[10px] text-slate-500">{msg.timestamp}</span>
              </div>

              {msg.type === 'diagnostic' && msg.diagnostic ? (
                <DiagnosticCard 
                  diagnostic={msg.diagnostic} 
                  onAction={handleDiagnosticAction}
                />
              ) : (
                <div className={`p-3 rounded-lg text-sm leading-relaxed shadow-sm ${
                  msg.role === 'user' 
                    ? 'bg-indigo-600/20 text-indigo-100 border border-indigo-500/30' 
                    : 'bg-slate-800 text-slate-200 border border-slate-700'
                }`}>
                  {msg.content}
                </div>
              )}
            </div>
          </div>
        ))}

        {isStreaming && streamingSteps.length > 0 && (
          <div className="flex gap-4">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-lg bg-blue-600 shadow-blue-500/20">
              <Cpu className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1 opacity-70">
                <span className="text-xs font-bold text-slate-300">DevOps Copilot</span>
                <span className="text-[10px] text-slate-500">{new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
              <DynamicReasoning steps={streamingSteps} isStreaming={true} />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t border-slate-800 bg-slate-900/50 backdrop-blur-md">
        <div className="relative max-w-4xl mx-auto flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Describe the incident or paste error logs..."
            className="flex-1 pr-12"
            disabled={isLoading}
          />
          <Button 
            onClick={handleSendMessage}
            disabled={isLoading}
            size="icon"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
