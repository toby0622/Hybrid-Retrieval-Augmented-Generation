import { useState } from 'react';
import { Save, X, Loader2, AlertTriangle } from 'lucide-react';
import { apiClient, DocumentChunk } from '@/lib/api';

interface DocumentEditorProps {
  document: DocumentChunk;
  onClose: (wasUpdated: boolean) => void;
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function DocumentEditor({ document, onClose, addToast }: DocumentEditorProps) {
  const [content, setContent] = useState(document.content);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    if (content === document.content) {
      onClose(false);
      return;
    }

    setIsSaving(true);
    try {
      await apiClient.updateDocument(document.id, content);
      addToast('Document updated successfully and re-indexed.', 'success');
      onClose(true); // Close and signal update
    } catch (error) {
      console.error('Update error:', error);
      addToast('Failed to update document.', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-4xl h-[80vh] flex flex-col shadow-2xl animate-in zoom-in-95 duration-200">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 rounded-t-xl">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Edit Document</h2>
          <div className="text-xs text-slate-500 font-mono mt-1">ID: {document.id} | {document.metadata.title}</div>
        </div>
        <button 
          onClick={() => onClose(false)}
          className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
          disabled={isSaving}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="bg-amber-500/10 border-b border-amber-500/20 p-3 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <p className="text-sm text-amber-200/80">
          Modifying this content will regenerate its vector embedding. 
          This affects semantic search results but does not modify the original source file.
        </p>
      </div>
      
      <div className="flex-1 p-4 overflow-hidden flex flex-col">
        <label className="text-sm font-medium text-slate-400 mb-2">Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="flex-1 w-full bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          placeholder="Document content..."
          disabled={isSaving}
        />
      </div>
      
      <div className="p-4 border-t border-slate-800 bg-slate-900/50 rounded-b-xl flex justify-end gap-3">
        <button
          onClick={() => onClose(false)}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          disabled={isSaving}
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving || content === document.content}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-all shadow-lg shadow-blue-900/20"
        >
          {isSaving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" /> Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" /> Save Changes
            </>
          )}
        </button>
      </div>
    </div>
  );
}
