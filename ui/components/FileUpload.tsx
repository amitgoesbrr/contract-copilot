"use client";

import { useRef, useState } from "react";

interface FileUploadProps {
  onFileUpload: (file: File) => void;
}

export default function FileUpload({ onFileUpload }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFile = (file: File) => {
    // Validate file type
    const validTypes = ["application/pdf", "text/plain", "text/markdown"];
    if (!validTypes.includes(file.type)) {
      alert("Please upload a PDF or text file");
      return;
    }

    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert("File size must be less than 10MB");
      return;
    }

    onFileUpload(file);
  };

  return (
    <div className="mt-8">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative w-full p-4 sm:p-8 text-center bg-white dark:bg-slate-800/50 border-2 border-dashed rounded-lg shadow-sm transition-colors duration-200 ${
          isDragging
            ? "border-primary bg-indigo-50 dark:bg-indigo-900/20"
            : "border-slate-300 dark:border-slate-700"
        }`}
      >
        <div className="flex flex-col items-center justify-center space-y-4">
          <div className="flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/50">
            <span className="material-symbols-outlined text-primary text-3xl">
              upload
            </span>
          </div>
          <p className="text-lg text-slate-700 dark:text-slate-300">
            Drop your contract here or{" "}
            <span className="font-semibold text-primary hover:underline cursor-pointer">
              click to browse
            </span>
          </p>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Supports PDF and TXT files up to 10MB
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          onChange={handleFileSelect}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          aria-label="Upload contract file"
        />
      </div>
    </div>
  );
}
