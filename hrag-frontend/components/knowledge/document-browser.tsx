import { useState, useEffect } from 'react';
import { Search, Edit2, ChevronLeft, ChevronRight, X, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { apiClient, DocumentChunk } from '@/lib/api';
import { DocumentEditor } from '@/components/knowledge/document-editor';

interface DocumentBrowserProps {
  isOpen: boolean;
  onClose: () => void;
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function DocumentBrowser({ isOpen, onClose, addToast }: DocumentBrowserProps) {
  const [documents, setDocuments] = useState<DocumentChunk[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [offset, setOffset] = useState<string | undefined>(undefined);
  const [selectedDoc, setSelectedDoc] = useState<DocumentChunk | null>(null);
  const [pageHistory, setPageHistory] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  
  const loadDocuments = async (nextOffset?: string, searchTerm?: string) => {
    setIsLoading(true);
    try {
      const docs = await apiClient.getDocuments(10, nextOffset, searchTerm);
      if (docs.length > 0) {
        setDocuments(docs);
      } else if (searchTerm) {
          setDocuments([]);
      }
    } catch (error) {
      console.error('Failed to load documents', error);
      addToast('Failed to load documents.', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
    if (isOpen) {
      loadDocuments(undefined, searchQuery);
    }
    }
  }, [isOpen]);

  const handleEdit = (doc: DocumentChunk) => {
    setSelectedDoc(doc);
  };

  const handleEditorClose = (wasUpdated: boolean) => {
    setSelectedDoc(null);
    if (wasUpdated) {
    if (wasUpdated) {
      loadDocuments(undefined, searchQuery); // Reload to see changes
    }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      {selectedDoc ? (
        <DocumentEditor 
          document={selectedDoc} 
          onClose={handleEditorClose} 
          addToast={addToast} 
        />
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-4xl h-[80vh] flex flex-col shadow-2xl">
          <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 rounded-t-xl">
            <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <Search className="w-5 h-5 text-blue-400" />
              Indexed Documents
            </h2>
            <div className="flex-1 max-w-sm ml-8 mr-4">
                <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search content..."
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-8 pr-4 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && loadDocuments(undefined, searchQuery)}
                    />
                </div>
            </div>
            <button  
              onClick={onClose}
              className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin scrollbar-thumb-slate-700">
            {isLoading && documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <Loader2 className="w-8 h-8 animate-spin mb-2" />
                <p>Loading documents...</p>
              </div>
            ) : (
              documents.map((doc) => (
                <Card key={doc.id} className="hover:border-slate-600 transition-all group">
                  <CardContent className="p-4 flex items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono text-slate-500">#{doc.id}</span>
                        <h3 className="font-semibold text-slate-200 truncate">
                          {doc.metadata.title || 'Untitled Document'}
                        </h3>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                          {doc.metadata.doc_type || 'chunk'}
                        </span>
                      </div>
                      <p className="text-sm text-slate-400 line-clamp-2 font-mono bg-slate-950/50 p-2 rounded">
                        {doc.content}
                      </p>
                    </div>
                    
                    <button
                      onClick={() => handleEdit(doc)}
                      className="p-2 bg-slate-800 hover:bg-blue-600 hover:text-white rounded-lg text-slate-400 transition-colors"
                      title="Edit Content"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
          
          <div className="p-4 border-t border-slate-800 bg-slate-900/50 rounded-b-xl flex justify-between items-center text-xs text-slate-500">
            <div>Showing {documents.length} items</div>
            {/* Pagination controls could go here if API supported standardized pagination response */}
          </div>
        </div>
      )}
    </div>
  );
}
