export interface SlotInfo {
  service_name?: string;
  error_type?: string;
  timestamp?: string;
  environment?: string;
  cluster?: string;
  additional_context?: string;
}

export interface RetrievalResult {
  source: 'graph' | 'vector' | 'mcp_tool';
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  confidence: number;
  raw_data?: unknown;
}

export interface DiagnosticStep {
  id: string;
  source: string;
  title: string;
  detail: string;
  status: 'info' | 'warning' | 'error';
  is_root?: boolean;
  is_parallel?: boolean;
  raw_content: {
    type: 'log' | 'graph' | 'markdown';
    data: unknown;
  };
}

export interface DiagnosticResponse {
  path: DiagnosticStep[];
  suggestion: string;
  confidence: number;
}

export interface ReasoningStep {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'completed';
}

export interface ChatResponse {
  thread_id: string;
  response: string;
  intent?: string;
  response_type: 'text' | 'reasoning' | 'diagnostic' | 'clarification';
  reasoning_steps?: ReasoningStep[];
  diagnostic?: DiagnosticResponse;
  clarification_question?: string;
}

export interface Message {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  type?: 'text' | 'reasoning' | 'diagnostic';
  reasoning_steps?: ReasoningStep[];
  diagnostic?: DiagnosticResponse;
}

export interface EntityConflict {
  id: string;
  type: 'conflict' | 'new';
  entity_name: string;
  source: string;
  confidence: number;
  existing_entity?: {
    name: string;
    desc: string;
  };
  new_entity: {
    name: string;
    desc: string;
  };
  description?: string;
}

export interface GardenerTask {
  id: number;
  type: 'conflict' | 'new';
  entityName: string;
  source: string;
  confidence: number;
  existingEntity?: {
    name: string;
    desc: string;
  };
  newEntity?: {
    name: string;
    desc: string;
  };
  desc?: string;
}

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'info' | 'error';
}

export type TabType = 'copilot' | 'knowledge';
