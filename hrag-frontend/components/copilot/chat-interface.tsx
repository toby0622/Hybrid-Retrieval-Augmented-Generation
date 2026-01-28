"use client";

import { useState, useRef, useEffect } from 'react';
import { Cpu, Database, ChevronRight } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { DynamicReasoning } from './dynamic-reasoning';
import { DiagnosticCard } from './diagnostic-card';
import { Message, DiagnosticStep, ReasoningStep } from '@/types';

// Initial system message
const INITIAL_MESSAGES: Message[] = [
  {
    id: 1,
    role: 'system',
    content: 'DevOps Copilot Online. Connected to Neo4j (Graph) and Qdrant (Vector). Ready for queries.',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
];

interface ChatInterfaceProps {
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function ChatInterface({ addToast }: ChatInterfaceProps) {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>(INITIAL_MESSAGES);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleDiagnosticAction = (actionType: 'case_study' | 'resolve') => {
    if (actionType === 'case_study') {
      addToast('Generated new Case Study draft from incident analysis.', 'success');
    } else if (actionType === 'resolve') {
      addToast('Incident marked resolved. Feedback loop updated.', 'success');
    }
  };

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now(),
      role: 'user',
      content: input,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    const lowerInput = input.toLowerCase();
    
    // Simulate API call with demo responses
    setTimeout(() => {
      // Path 1: Greeting/Help
      if (lowerInput.match(/^(hi|hello|hey|help|who are you)/)) {
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'assistant',
          content: 'Hello! I am your DevOps Copilot. I can help investigate incidents, analyze logs, and query the Knowledge Graph. Please provide specific error logs or incident details to start.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }]);
        setIsLoading(false);
        return;
      }

      // Path 2: Incident Diagnosis Demo
      if (lowerInput.includes('latency') || lowerInput.includes('payment') || lowerInput.includes('slow') || lowerInput.includes('error') || lowerInput.includes('timeout')) {
        // First add reasoning message
        const reasoningSteps: ReasoningStep[] = [
          { id: 'step1', label: 'Input Guardrails: Incident Query detected.', status: 'completed' },
          { id: 'step2', label: 'Slot Filling: Context implies "prod-cluster-alpha".', status: 'completed' },
          { id: 'step3', label: 'Hybrid Retrieval: Neo4j (Topology) + Qdrant (Docs).', status: 'completed' },
          { id: 'step4', label: 'MCP Tool: Executed SQL query on `metrics_db`.', status: 'completed' },
        ];
        
        const reasoningMsg: Message = {
          id: Date.now() + 1,
          role: 'assistant',
          type: 'reasoning',
          reasoning_steps: reasoningSteps,
          content: 'Analysis in progress...',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, reasoningMsg]);

        // Then add diagnostic after delay
        setTimeout(() => {
          const diagnosticPath: DiagnosticStep[] = [
            { 
              id: 'p1',
              source: 'Log Analysis', 
              title: 'Trigger: Connection Pool Exhausted',
              detail: 'Error: Connection Pool Exhausted in Payment-Service', 
              status: 'error',
              is_root: true,
              raw_content: {
                type: 'log',
                data: '[2025-11-25 09:30:01.241] ERROR [PaymentService] HikariPool-1 - Connection is not available...'
              }
            },
            { 
              id: 'p2',
              source: 'Graph Topology', 
              title: 'Context: Deployment',
              detail: 'v2.4.1-hotfix deployed @ 09:15', 
              status: 'warning',
              is_parallel: true,
              raw_content: {
                type: 'graph',
                data: {
                  node: 'PaymentService',
                  relationship: 'DEPLOYED_ON',
                  properties: { version: 'v2.4.1-hotfix' }
                }
              }
            },
            { 
              id: 'p3',
              source: 'Vector Search', 
              title: 'Context: Post-Mortem',
              detail: 'Ref: Post-Mortem #402 (HikariCP)', 
              status: 'info',
              is_parallel: true,
              raw_content: {
                type: 'markdown',
                data: '**Post-Mortem #402 Summary**\nRoot Cause: HikariCP pool size reset.'
              }
            }
          ];

          const diagnosticMsg: Message = {
            id: Date.now() + 2,
            role: 'assistant',
            type: 'diagnostic',
            content: '根據混合檢索與日誌分析，發現潛在根因。',
            diagnostic: {
              path: diagnosticPath,
              suggestion: '建議檢查 `Payment-Service` 的 HikariCP 設定。新版本部署可能重置了 `maximum-pool-size` 參數。',
              confidence: 0.87
            },
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          setMessages(prev => [...prev, diagnosticMsg]);
          setIsLoading(false);
        }, 2000);
        return;
      }

      // Path 3: Fallback
      setMessages(prev => [...prev, {
        id: Date.now(),
        role: 'assistant',
        content: 'I did not recognize a specific incident pattern. Could you provide more details, such as error logs, service names, or timestamps?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }]);
      setIsLoading(false);
    }, 800);
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 relative overflow-hidden">
      {/* Header */}
      <div className="h-16 border-b border-slate-800 flex items-center px-6 bg-slate-950/80 backdrop-blur-sm z-10 sticky top-0">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
            Incident Response Copilot
            <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              System Healthy
            </span>
          </h2>
          <p className="text-xs text-slate-500">Retrieval: Hybrid (Graph + Vector) • Model: LLM-Reasoning-v2</p>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 rounded-md border border-slate-800 text-xs text-slate-400 hover:border-slate-600 transition-colors cursor-help" title="Connection Status: Active">
            <Database className="w-3 h-3" /> Neo4j Connected
          </div>
        </div>
      </div>

      {/* Messages */}
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

              {msg.type === 'reasoning' && msg.reasoning_steps ? (
                <DynamicReasoning steps={msg.reasoning_steps} />
              ) : msg.type === 'diagnostic' && msg.diagnostic ? (
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
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
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
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
