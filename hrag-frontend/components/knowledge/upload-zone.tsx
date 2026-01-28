"use client";

import { useRef } from 'react';
import { Upload, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface UploadZoneProps {
  isUploading: boolean;
  onFileSelect: (file: File) => void;
}

export function UploadZone({ isUploading, onFileSelect }: UploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect(file);
    }
  };

  return (
    <div 
      onClick={() => !isUploading && fileInputRef.current?.click()}
      className={cn(
        "border-2 border-dashed border-slate-700 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-900/30 hover:bg-slate-900/50 hover:border-blue-500/50 transition-all cursor-pointer group",
        isUploading && "opacity-70 pointer-events-none"
      )}
    >
      <input 
        type="file" 
        className="hidden" 
        ref={fileInputRef} 
        onChange={handleFileChange} 
        accept=".pdf,.md,.txt,.log"
      />
      
      <div className="p-4 rounded-full bg-slate-800 group-hover:scale-110 transition-transform mb-4">
        {isUploading ? (
          <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        ) : (
          <Upload className="w-8 h-8 text-slate-400 group-hover:text-blue-400" />
        )}
      </div>
      <h3 className="text-slate-200 font-semibold">
        {isUploading ? 'Ingesting Knowledge...' : 'Upload New Knowledge'}
      </h3>
      <p className="text-slate-500 text-sm mt-1">
        {isUploading ? 'Parsing document & extracting entities via LLM' : 'Drag & drop PDF, Markdown, or Log files here'}
      </p>
    </div>
  );
}
