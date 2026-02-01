/**
 * HRAG API Client
 * Connects frontend to backend FastAPI endpoints
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatRequest {
  query: string;
  thread_id?: string;
  feedback?: string;
  stream?: boolean;
}

export interface ReasoningStep {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'completed';
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

export interface ChatResponse {
  thread_id: string;
  response: string;
  intent?: string;
  response_type: 'text' | 'reasoning' | 'diagnostic' | 'clarification';
  reasoning_steps?: ReasoningStep[];
  diagnostic?: DiagnosticResponse;
  clarification_question?: string;
}

export interface StreamEvent {
  type: 'reasoning' | 'complete' | 'error';
  step?: ReasoningStep;
  thread_id?: string;
  response?: string;
  intent?: string;
  diagnostic?: DiagnosticResponse;
  clarification_question?: string;
  message?: string;
}

export interface UploadResponse {
  file_name: string;
  status: string;
  entities_extracted: number;
  conflicts_found: number;
  task_ids: string[];
}

export interface GardenerTask {
  id: string;
  type: 'conflict' | 'new';
  entity_name: string;
  source: string;
  confidence: number;
  existing_entity?: { name: string; description: string };
  new_entity: { name: string; description: string };
  description?: string;
}

export interface StatsResponse {
  indexed_documents: number;
  knowledge_nodes: number;
  pending_tasks: number;
  active_threads: number;
}

export interface HealthResponse {
  status: string;
  neo4j: string;
  qdrant: string;
  llm: string;
}

export interface IngestResponse {
  file_name: string;
  domain: string;
  status: string;
  entities_created: number;
  relations_created: number;
  vectors_created: number;
  errors: string[];
}

class HRAGApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  /**
   * Health check
   */
  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  /**
   * Get system statistics
   */
  async getStats(): Promise<StatsResponse> {
    return this.request<StatsResponse>('/stats');
  }

  /**
   * Send chat message (non-streaming)
   */
  async chat(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Send chat message with streaming (SSE)
   */
  async chatStream(
    request: ChatRequest,
    onStep: (step: ReasoningStep) => void,
    onComplete: (response: StreamEvent) => void,
    onError: (error: string) => void
  ): Promise<void> {
    const url = `${this.baseUrl}/chat/stream`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') {
              return;
            }
            
            try {
              const event: StreamEvent = JSON.parse(data);
              
              if (event.type === 'reasoning' && event.step) {
                onStep(event.step);
              } else if (event.type === 'complete') {
                onComplete(event);
              } else if (event.type === 'error') {
                onError(event.message || 'Unknown error');
              }
            } catch (parseError) {
              console.error('Parse error:', parseError, data);
            }
          }
        }
      }
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Unknown error');
    }
  }

  /**
   * Upload knowledge document
   */
  async uploadDocument(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseUrl}/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Upload Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  /**
   * Ingest document with schema-aware ETL pipeline
   * Automatically extracts entities to Neo4j and vectors to Qdrant
   */
  async ingestDocument(file: File, docType: string = 'document'): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', docType);

    const response = await fetch(`${this.baseUrl}/api/ingest`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Ingest Error: ${response.status} - ${error}`);
    }

    return response.json();
  }

  /**
   * Get gardener tasks
   */
  async getGardenerTasks(): Promise<{ tasks: GardenerTask[] }> {
    return this.request<{ tasks: GardenerTask[] }>('/gardener/tasks');
  }

  /**
   * Process gardener action
   */
  async gardenerAction(
    entityId: string,
    action: 'approve' | 'reject' | 'merge',
    modifiedEntity?: Record<string, unknown>
  ): Promise<{ status: string; message: string }> {
    return this.request('/gardener/action', {
      method: 'POST',
      body: JSON.stringify({
        entity_id: entityId,
        action,
        modified_entity: modifiedEntity,
      }),
    });
  }
}

// Export singleton instance
export const apiClient = new HRAGApiClient();

// Export class for custom instances
export { HRAGApiClient };
