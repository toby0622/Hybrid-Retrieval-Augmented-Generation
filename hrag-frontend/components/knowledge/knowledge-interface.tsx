"use client";

import { useState, useEffect } from 'react';
import { FileText, Network, AlertTriangle, CheckCircle2, RefreshCw, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { UploadZone } from './upload-zone';
import { EntityCard } from './entity-card';
import { DocumentBrowser } from './document-browser';
import { NodeBrowser } from './node-browser';
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
  const [isDocumentBrowserOpen, setIsDocumentBrowserOpen] = useState(false);
  const [isNodeBrowserOpen, setIsNodeBrowserOpen] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      try {
        const statsData = await apiClient.getStats();
        setStats({
          indexedDocuments: statsData.indexed_documents,
          knowledgeNodes: statsData.knowledge_nodes,
          pendingTasks: statsData.pending_tasks
        });
      } catch (error) {
        console.error('Stats error:', error);
        throw new Error('Failed to load stats from backend');
      }

      try {
        const tasksData = await apiClient.getGardenerTasks();
        const mappedTasks: GardenerTask[] = tasksData.tasks.map((t: ApiGardenerTask) => ({
          id: String(t.id),
          type: t.type,
          entity_name: t.entity_name,
          source: t.source,
          confidence: t.confidence,
          existing_entity: t.existing_entity ? {
            name: t.existing_entity.name,
            description: t.existing_entity.description
          } : undefined,
          new_entity: t.new_entity ? {
            name: t.new_entity.name,
            description: t.new_entity.description
          } : undefined,
          description: t.description
        }));
        setTasks(mappedTasks);
      } catch (error) {
        console.error('Tasks error:', error);
        throw new Error('Failed to load gardener tasks from backend');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResolve = async (id: string, action: 'approve' | 'reject') => {
    try {
      await apiClient.gardenerAction(id, action);
      setTasks(prev => prev.filter(t => t.id !== id));
      
      if (action === 'approve') {
        addToast('Entity successfully written to Knowledge Graph.', 'success');
      } else {
        addToast('Entity rejected and flagged for review.', 'info');
      }
    } catch (error) {
      console.error('Action error:', error);
      addToast(`Failed to ${action} entity. Backend service unavailable.`, 'error');
    }
  };

  const handleBulkResolve = async (action: 'approve' | 'reject') => {
    if (tasks.length === 0) return;
    
    setIsLoading(true);
    let successCount = 0;
    
    try {
      // Execute serially to prevent backend overload
      for (const task of tasks) {
        try {
          await apiClient.gardenerAction(task.id.toString(), action);
          successCount++;
        } catch (e) {
          console.error(`Failed to ${action} task ${task.id}:`, e);
        }
      }
      
      if (successCount === tasks.length) {
        addToast(`Successfully ${action}d all ${successCount} entities.`, 'success');
        setTasks([]);
      } else {
        addToast(`Processed ${successCount}/${tasks.length} entities. Some failed.`, 'error');
        await loadData(); // Reload to get remaining tasks
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    addToast(`Uploading ${file.name}...`, 'info');

    try {
      const response = await apiClient.ingestDocument(file, 'document');
      
      await loadData();
      
      if (response.status === 'success') {
        addToast(
          `Ingested ${file.name}: ${response.entities_created} entities, ${response.vectors_created} vectors`, 
          'success'
        );
      } else {
        addToast(
          `Partial ingestion: ${response.errors.join(', ')}`, 
          'info'
        );
      }
    } catch (error) {
      console.error('Upload error:', error);
      addToast('Upload failed. Backend service unavailable.', 'error');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700">
      <div className="p-8 pb-4">
        <h2 className="text-2xl font-bold text-slate-100 mb-6">Knowledge Base Ingestion</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card 
            className="cursor-pointer hover:bg-slate-900/50 transition-colors group relative"
            onClick={() => setIsDocumentBrowserOpen(true)}
          >
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 bg-blue-500/10 rounded-lg text-blue-400 group-hover:bg-blue-500/20 transition-colors">
                <FileText className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-200">
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : stats.indexedDocuments.toLocaleString()}
                </div>
                <div className="text-xs text-slate-500 group-hover:text-blue-400 transition-colors">Indexed Documents (Click to view)</div>
              </div>
            </CardContent>
          </Card>
          
          <Card
            className="cursor-pointer hover:bg-slate-900/50 transition-colors group relative"
            onClick={() => setIsNodeBrowserOpen(true)}
          >
            <CardContent className="p-4 flex items-center gap-4">
              <div className="p-3 bg-purple-500/10 rounded-lg text-purple-400 group-hover:bg-purple-500/20 transition-colors">
                <Network className="w-6 h-6" />
              </div>
              <div>
                <div className="text-2xl font-bold text-slate-200">
                  {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : stats.knowledgeNodes.toLocaleString()}
                </div>
                <div className="text-xs text-slate-500 group-hover:text-purple-400 transition-colors">Knowledge Nodes (Click to view)</div>
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

        <div className="mb-8">
          <UploadZone isUploading={isUploading} onFileSelect={handleFileUpload} />
        </div>

        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            The Gardener Review 
            <span className="text-xs font-normal text-slate-500 bg-slate-900 px-2 py-1 rounded border border-slate-800">Human-in-the-Loop</span>
          </h3>
          <div className="flex items-center gap-3">
            {tasks.length > 1 && (
              <div className="flex items-center gap-2 mr-2">
                 <button
                    onClick={() => handleBulkResolve('approve')}
                    disabled={isLoading}
                    className="text-xs bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 px-3 py-1.5 rounded-md border border-emerald-500/20 transition-colors disabled:opacity-50"
                 >
                   Approve All
                 </button>
                 <button
                    onClick={() => handleBulkResolve('reject')}
                    disabled={isLoading}
                    className="text-xs bg-red-500/10 text-red-400 hover:bg-red-500/20 px-3 py-1.5 rounded-md border border-red-500/20 transition-colors disabled:opacity-50"
                 >
                   Reject All
                 </button>
              </div>
            )}
            <button 
              onClick={() => {
                loadData();
                addToast('Queue refreshed.', 'info');
              }} 
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 transition-colors"
              disabled={isLoading}
            >
              <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>
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

      <DocumentBrowser 
        isOpen={isDocumentBrowserOpen} 
        onClose={() => setIsDocumentBrowserOpen(false)} 
        addToast={addToast} 
      />

      <NodeBrowser
        isOpen={isNodeBrowserOpen}
        onClose={() => setIsNodeBrowserOpen(false)}
        addToast={addToast}
      />
    </div>
  );
}
