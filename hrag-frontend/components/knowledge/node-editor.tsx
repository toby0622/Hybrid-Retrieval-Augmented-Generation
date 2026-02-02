import { useState } from 'react';
import { Save, X, Trash2, Plus } from 'lucide-react';
import { apiClient, NodeEntity } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface NodeEditorProps {
  node: NodeEntity;
  onClose: (wasUpdated: boolean) => void;
  addToast: (message: string, type: 'success' | 'info' | 'error') => void;
}

export function NodeEditor({ node, onClose, addToast }: NodeEditorProps) {
  const [properties, setProperties] = useState<Array<{ key: string; value: string }>>(
    Object.entries(node.properties).map(([key, value]) => ({ 
      key, 
      value: String(value) // Convert all to string for simple editing currently
    }))
  );
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Reconstruct properties object
      const propsObj: Record<string, unknown> = {};
      properties.forEach(p => {
        if (p.key.trim()) {
           // Try to infer type? For now keep simple and save as string unless it looks strictly numeric.
           // However Neo4j is typed. If the user edits "123", should it correspond to int or string?
           // The safest for a generic editor without schema awareness is string, or try parsing.
           // Let's keep as string or try rudimentary number parsing.
           const num = Number(p.value);
           if (!isNaN(num) && p.value.trim() !== '') {
               propsObj[p.key] = num;
           } else {
               propsObj[p.key] = p.value;
           }
        }
      });

      await apiClient.updateNode(node.id, propsObj);
      addToast('Node updated successfully.', 'success');
      onClose(true);
    } catch (error) {
      console.error('Failed to update node', error);
      addToast('Failed to update node.', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const updateProperty = (index: number, field: 'key' | 'value', newValue: string) => {
    const newProps = [...properties];
    newProps[index][field] = newValue;
    setProperties(newProps);
  };

  const removeProperty = (index: number) => {
    setProperties(properties.filter((_, i) => i !== index));
  };

  const addProperty = () => {
    setProperties([...properties, { key: '', value: '' }]);
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-2xl flex flex-col shadow-2xl max-h-[90vh]">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50 rounded-t-xl">
        <h2 className="text-xl font-bold text-slate-100">Edit Node</h2>
        <button 
          onClick={() => onClose(false)}
          className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-4 border-b border-slate-800 bg-slate-900/30">
        <div className="flex flex-wrap gap-2 mb-2">
            {node.labels.map(label => (
                <span key={label} className="text-sm px-2 py-1 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-medium">
                {label}
                </span>
            ))}
        </div>
        <div className="text-xs font-mono text-slate-500">ID: {node.id}</div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {properties.map((prop, index) => (
          <div key={index} className="flex items-center gap-2 group">
            <Input
              value={prop.key}
              onChange={(e) => updateProperty(index, 'key', e.target.value)}
              placeholder="Key"
              className="flex-1 bg-slate-950 border-slate-800 text-slate-200"
            />
            <span className="text-slate-600">:</span>
            <Input
              value={prop.value}
              onChange={(e) => updateProperty(index, 'value', e.target.value)}
              placeholder="Value"
              className="flex-[2] bg-slate-950 border-slate-800 text-slate-200"
            />
            <button
              onClick={() => removeProperty(index)}
              className="p-2 text-slate-600 hover:text-red-400 hover:bg-red-900/20 rounded transition-colors"
              title="Remove Property"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}

        <button
            onClick={addProperty}
            className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 px-2 py-2 rounded hover:bg-blue-900/20 transition-colors w-full justify-center border border-dashed border-slate-700 hover:border-blue-500/50"
        >
            <Plus className="w-4 h-4" /> Add Property
        </button>
      </div>
      
      <div className="p-4 border-t border-slate-800 bg-slate-900/50 rounded-b-xl flex justify-end gap-2">
        <button
          onClick={() => onClose(false)}
          className="px-4 py-2 hover:bg-slate-800 text-slate-300 rounded-lg transition-colors"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? <span className="animate-spin text-white">⏳</span> : <Save className="w-4 h-4" />}
          Save Changes
        </button>
      </div>
    </div>
  );
}
