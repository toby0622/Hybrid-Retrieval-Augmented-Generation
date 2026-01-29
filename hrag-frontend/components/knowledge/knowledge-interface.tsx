"use client";

import { useState, useEffect } from 'react';
import { FileText, Network, AlertTriangle, CheckCircle2, RefreshCw, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { UploadZone } from './upload-zone';
import { EntityCard } from './entity-card';
import { GardenerTask } from '@/types';
import { apiClient, GardenerTask as ApiGardenerTask } from '@/lib/api';

interface KnowledgeInterfaceProps {
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function KnowledgeInterface({ addToast }: KnowledgeInterfaceProps) {
  const [tasks, setTasks] = useState<GardenerTask[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    indexedDocuments: 0,
    knowledgeNodes: 0,
    pendingTasks: 0
  });

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      // Load stats
      try {
        const statsData = await apiClient.getStats();
        setStats({
          indexedDocuments: statsData.indexed_documents,
          knowledgeNodes: statsData.knowledge_nodes,
          pendingTasks: statsData.pending_tasks
        });
      } catch (error) {
        console.error('Stats error:', error);
        // Use mock data matching init_db.py on error
        setStats({
          indexedDocuments: 8,  // 8 documents in Qdrant
          knowledgeNodes: 17,   // 17 nodes in Neo4j
          pendingTasks: 2
        });
      }

      // Load gardener tasks
      try {
        const tasksData = await apiClient.getGardenerTasks();
        const mappedTasks: GardenerTask[] = tasksData.tasks.map((t: ApiGardenerTask) => ({
          id: parseInt(t.id) || Date.now(),
          type: t.type,
          entityName: t.entity_name,
          source: t.source,
          confidence: t.confidence,
          existingEntity: t.existing_entity ? {
            name: t.existing_entity.name,
            desc: t.existing_entity.description
          } : undefined,
          newEntity: t.new_entity ? {
            name: t.new_entity.name,
            desc: t.new_entity.description
          } : undefined,
          desc: t.description
        }));
        setTasks(mappedTasks);
      } catch (error) {
        console.error('Tasks error:', error);
        // Use mock data on error
        setTasks([
          {
            id: 101,
            type: 'conflict',
            entityName: 'PaymentGateway_Timeout',
            source: 'Post-Mortem-2025-10.pdf',
            confidence: 0.92,
            existingEntity: {
              name: 'Payment_Timeout_Config',
              desc: 'Default timeout set to 3000ms in config map.'
            },
            newEntity: {
              name: 'PaymentGateway_Timeout',
              desc: 'Timeout observed at 5000ms during peak load.'
            }
          },
          {
            id: 102,
            type: 'new',
            entityName: 'Redis_Cluster_Bravo',
            source: 'Infra_Topology_Update.md',
            confidence: 0.98,
            desc: 'New Redis cluster provisioned for caching layer in region ap-northeast-1.'
          }
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolve = async (id: number, action: 'approve' | 'reject') => {
    try {
      await apiClient.gardenerAction(id.toString(), action);
      setTasks(prev => prev.filter(t => t.id !== id));
      
      if (action === 'approve') {
        addToast('Entity successfully written to Knowledge Graph.', 'success');
      } else {
        addToast('Entity rejected and flagged for review.', 'info');
      }
    } catch (error) {
      console.error('Action error:', error);
      // Still update UI on error (optimistic update)
      setTasks(prev => prev.filter(t => t.id !== id));
      addToast(action === 'approve' ? 'Entity approved (mock mode).' : 'Entity rejected (mock mode).', 'info');
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    addToast(`Uploading ${file.name}...`, 'info');

    try {
      const response = await apiClient.uploadDocument(file);
      
      // Reload tasks to get new entities
      await loadData();
      addToast(`Extracted ${response.entities_extracted} entities from ${file.name}`, 'success');
    } catch (error) {
      console.error('Upload error:', error);
      
      // Mock response on error
      const newTask: GardenerTask = {
        id: Date.now(),
        type: 'new',
        entityName: 'New_Entity_From_Upload',
        source: file.name,
        confidence: 0.85,
        desc: 'Automatically extracted entity from uploaded document.'
      };
      setTasks(prev => [newTask, ...prev]);
      addToast('File parsed and new entities extracted (mock mode).', 'success');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
      <div className="p-8 pb-4">
        <h2 className="text-2xl font-bold text-slate-100 mb-6">Knowledge Base Ingestion</h2>
        
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400">
                <FileText className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-200">
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : stats.indexedDocuments.toLocaleString()}
                </div>
                <div className="text-xs text-slate-500">Indexed Documents</div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 bg-purple-500/10 rounded-lg text-purple-400">
                <Network className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-200">
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : stats.knowledgeNodes.toLocaleString()}
                </div>
                <div className="text-xs text-slate-500">Knowledge Nodes</div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 bg-amber-500/10 rounded-lg text-amber-400">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-200">{tasks.length}</div>
                <div className="text-xs text-slate-500">Gardener Tasks Pending</div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Upload Area */}
        <div className="mb-8">
          <UploadZone isUploading={isUploading} onFileSelect={handleFileUpload} />
        </div>

        {/* Gardener Review Section */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            The Gardener Review 
            <span className="text-xs font-normal text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">Human-in-the-Loop</span>
          </h3>
          <button 
            onClick={() => {
              loadData();
              addToast('Queue refreshed.', 'info');
            }} 
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
            disabled={isLoading}
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} /> Refresh Queue
          </button>
        </div>

        {isLoading ? (
          <Card>
            <CardContent className="p-8 text-center text-slate-500 flex flex-col items-center">
              <Loader2 className="w-12 h-12 text-slate-700 mb-2 animate-spin" />
              <p>Loading tasks...</p>
            </CardContent>
          </Card>
        ) : tasks.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-slate-500 flex flex-col items-center">
              <CheckCircle2 className="w-12 h-12 text-slate-700 mb-2" />
              <p>All entities aligned and processed.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pb-8">
            {tasks.map(task => (
              <EntityCard key={task.id} task={task} onResolve={handleResolve} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
