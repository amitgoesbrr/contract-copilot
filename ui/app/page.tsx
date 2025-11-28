"use client";

import Disclaimer from "@/components/Disclaimer";
import FileUpload from "@/components/FileUpload";
import LockScreen from "@/components/LockScreen";
import ProgressIndicator from "@/components/ProgressIndicator";
import ResultsDisplay from "@/components/ResultsDisplay";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function HomeContent() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const searchParams = useSearchParams();
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const sessionParam = searchParams.get("session");
    if (sessionParam && !results) {
      loadSession(sessionParam);
    }
  }, [searchParams]);

  const loadSession = async (id: string) => {
    setIsProcessing(true);
    setSessionId(id);
    try {
      const response = await fetch(`${API_URL}/results/${id}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to load session");
      }
      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError("Failed to load session history.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFileUpload = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      // Upload contract
      const uploadResponse = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      if (!uploadResponse.ok) {
        throw new Error("Upload failed");
      }

      const uploadData = await uploadResponse.json();
      setSessionId(uploadData.session_id);

      // Poll for results
      let completed = false;
      while (!completed) {
        await new Promise((resolve) => setTimeout(resolve, 2000));

        const statusResponse = await fetch(
          `${API_URL}/status/${uploadData.session_id}`,
          {
            credentials: "include",
          }
        );
        const statusData = await statusResponse.json();

        if (statusData.status === "completed") {
          completed = true;
          const resultsResponse = await fetch(
            `${API_URL}/results/${uploadData.session_id}`,
            {
              credentials: "include",
            }
          );
          const resultsData = await resultsResponse.json();
          setResults(resultsData);
        } else if (statusData.status === "failed") {
          throw new Error(statusData.error || "Processing failed");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setSessionId(null);
    setIsProcessing(false);
    setResults(null);
    setError(null);
    // Clear URL param
    window.history.pushState({}, "", "/");
  };

  return (
    <LockScreen>
      <div className="flex flex-col min-h-screen bg-slate-50 dark:bg-slate-900 font-display text-slate-800 dark:text-slate-200 antialiased">
        <header className="w-full flex justify-end p-4 md:p-8">
          <Link
            href="/history"
            className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-primary dark:hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined text-base">history</span>
            <span>History</span>
          </Link>
        </header>

        <main className="flex-grow flex items-center justify-center p-4">
          <div className="w-full max-w-3xl mx-auto px-4">
            <div className="text-center mb-8">
              <h1 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-white">
                AI Contract Reviewer & Negotiation Copilot
              </h1>
              <p className="mt-3 text-slate-600 dark:text-slate-400">
                Automated contract analysis powered by Google ADK and Gemini
              </p>
            </div>

            <Disclaimer />

            {error && (
              <div className="mt-8 w-full p-4 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700/50 flex items-start space-x-3">
                <span className="material-symbols-outlined text-red-500 dark:text-red-400 mt-0.5">
                  error
                </span>
                <div className="flex-1">
                  <p className="font-semibold text-sm text-red-800 dark:text-red-300">
                    Error
                  </p>
                  <p className="text-sm text-red-700 dark:text-red-400 mt-1">
                    {error}
                  </p>
                  <Button
                    onClick={handleReset}
                    variant="outline"
                    size="sm"
                    className="mt-3"
                  >
                    Try Again
                  </Button>
                </div>
              </div>
            )}

            {!isProcessing && !results && !error && (
              <FileUpload onFileUpload={handleFileUpload} />
            )}

            {isProcessing && <ProgressIndicator />}

            {results && (
              <div className="w-full max-w-7xl mt-8">
                <ResultsDisplay
                  results={results}
                  sessionId={sessionId}
                  onReset={handleReset}
                />
              </div>
            )}
          </div>
        </main>
      </div>
    </LockScreen>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-slate-900">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      }
    >
      <HomeContent />
    </Suspense>
  );
}
