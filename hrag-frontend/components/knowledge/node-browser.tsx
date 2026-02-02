import { useState, useEffect } from 'react';
import { Network, Edit2, X, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { apiClient, NodeEntity } from '@/lib/api';
import { NodeEditor } from '@/components/knowledge/node-editor';

interface NodeBrowserProps {
  isOpen: boolean;
  onClose: () => void;
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function NodeBrowser({ isOpen, onClose, addToast }: NodeBrowserProps) {
  const [nodes, setNodes] = useState<NodeEntity[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [selectedNode, setSelectedNode] = useState<NodeEntity | null>(null);

  const loadNodes = async (reset = false) => {
    setIsLoading(true);
    try {
      const currentOffset = reset ? 0 : offset;
      const fetchedNodes = await apiClient.getNodes(50, currentOffset);
      if (reset) {
        setNodes(fetchedNodes);
        setOffset(fetchedNodes.length);
      } else {
        setNodes(prev => [...prev, ...fetchedNodes]);
        setOffset(prev => prev + fetchedNodes.length);
      }
    } catch (error) {
      console.error('Failed to load nodes', error);
      addToast('Failed to load knowledge nodes.', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadNodes(true);
    }
  }, [isOpen]);

  const handleEdit = (node: NodeEntity) => {
    setSelectedNode(node);
  };

  const handleEditorClose = (wasUpdated: boolean) => {
    setSelectedNode(null);
    if (wasUpdated) {
      loadNodes(true); // Reload to see changes
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      {selectedNode ? (
        <NodeEditor 
          node={selectedNode} 
          onClose={handleEditorClose} 
          addToast={addToast} 
        />
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-4xl h-[80vh] flex flex-col shadow-2xl">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 rounded-t-xl">
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Network className="w-5 h-5 text-purple-400" />
              Knowledge Graph Nodes
            </h2>
            <button 
              onClick={onClose}
              className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-slate-700">
            {isLoading && nodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <Loader2 className="w-8 h-8 animate-spin mb-2" />
                <p>Loading nodes...</p>
              </div>
            ) : nodes.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500">
                    <p>No nodes found in the graph.</p>
                </div>
            ) : (
              nodes.map((node) => (
                <Card key={node.id} className="hover:border-slate-600 transition-all group border-slate-800 bg-slate-950/50">
                  <CardContent className="p-4 flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-mono text-slate-500">ID: {node.id}</span>
                        {node.labels.map(label => (
                          <span key={label} className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                            {label}
                          </span>
                        ))}
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(node.properties).slice(0, 4).map(([key, value]) => (
                          <div key={key} className="truncate text-slate-400">
                            <span className="text-slate-500 font-medium mr-1">{key}:</span>
                            {String(value)}
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    <button
                      onClick={() => handleEdit(node)}
                      className="p-2 bg-slate-800 hover:bg-blue-600 hover:text-white rounded-lg text-slate-400 transition-colors opacity-0 group-hover:opacity-100"
                      title="Edit Node"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </CardContent>
                </Card>
              ))
            )}
             {/* Simple Load More Trigger if needed, or infinite scroll. For now using initial load of 50. */}
          </div>
          
          <div className="p-4 border-t border-slate-800 bg-slate-900/50 rounded-b-xl flex justify-between items-center text-xs text-slate-500">
            <div>Showing {nodes.length} nodes</div>
            <button 
                onClick={() => loadNodes()} 
                disabled={isLoading}
                className="hover:text-purple-400 transition-colors disabled:opacity-50"
            >
                {isLoading ? 'Loading...' : 'Load More'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
