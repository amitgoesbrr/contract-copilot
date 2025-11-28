"use client";

import LockScreen from "@/components/LockScreen";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ArrowLeft, Calendar, Clock, FileText, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SessionSummary {
  session_id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  filename: string;
}

export default function HistoryPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const response = await fetch(`${API_URL}/sessions`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to fetch sessions");
      }
      const data = await response.json();
      setSessions(data);
    } catch (err) {
      console.error("Error fetching sessions:", err);
      setError("Failed to load history. Please try again later.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (sessionId: string, filename: string) => {
    window.open(`${API_URL}/sessions/${sessionId}/file`, "_blank");
  };

  const handleDelete = async (sessionId: string) => {
    try {
      setDeletingId(sessionId);
      const response = await fetch(`${API_URL}/sessions/${sessionId}`, {
        method: "DELETE",
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error("Failed to delete session");
      }

      // Remove from list
      setSessions(sessions.filter((s) => s.session_id !== sessionId));
    } catch (err) {
      console.error("Error deleting session:", err);
      alert("Failed to delete session. Please try again.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <LockScreen>
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 font-sans">
        <div className="flex flex-col min-h-screen">
          <main className="flex-grow container mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
            <div className="max-w-4xl mx-auto">
              <div className="mb-8">
                <Link
                  href="/"
                  className="inline-flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-500 transition-colors"
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Analysis
                </Link>
              </div>

              <div className="text-center md:text-left mb-8">
                <h1 className="text-3xl md:text-4xl font-bold text-slate-900 dark:text-slate-100">
                  Analysis History
                </h1>
                <p className="mt-2 text-slate-600 dark:text-slate-400">
                  View and manage your past contract reviews
                </p>
              </div>

              {loading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                  <p className="text-slate-500">Loading history...</p>
                </div>
              ) : error ? (
                <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center text-red-600">
                  {error}
                </div>
              ) : sessions.length === 0 ? (
                <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-dashed border-slate-300 dark:border-slate-700 p-12 text-center">
                  <FileText className="h-12 w-12 text-slate-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-900 dark:text-slate-100">
                    No history yet
                  </h3>
                  <p className="text-slate-500 dark:text-slate-400 mt-2 mb-6">
                    Start by uploading a contract for analysis.
                  </p>
                  <Link href="/">
                    <button className="bg-blue-600 text-white font-medium py-2 px-4 rounded-md text-sm hover:bg-blue-700 transition-colors">
                      Start Analysis
                    </button>
                  </Link>
                </div>
              ) : (
                <div className="space-y-4">
                  {sessions.map((session) => (
                    <div
                      key={session.session_id}
                      className="flex flex-col md:flex-row items-center justify-between p-4 bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-transparent hover:border-blue-500 transition-all duration-300 group"
                    >
                      <div className="flex items-center w-full md:w-auto mb-4 md:mb-0">
                        <div className="bg-blue-100 dark:bg-blue-900/40 p-3 rounded-lg mr-4">
                          <FileText className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div>
                          <p className="font-semibold text-slate-800 dark:text-slate-200">
                            {session.filename || "Unknown Contract"}
                          </p>
                          <div className="flex items-center text-sm text-slate-500 dark:text-slate-400 mt-1 space-x-3">
                            <div className="flex items-center">
                              <Calendar className="h-4 w-4 mr-1.5" />
                              <span>
                                {new Date(
                                  session.created_at
                                ).toLocaleDateString(undefined, {
                                  dateStyle: "medium",
                                })}
                              </span>
                            </div>
                            <div className="flex items-center">
                              <Clock className="h-4 w-4 mr-1.5" />
                              <span>
                                {new Date(
                                  session.created_at
                                ).toLocaleTimeString(undefined, {
                                  timeStyle: "short",
                                })}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-3 w-full md:w-auto">
                        <Link
                          href={`/?session=${session.session_id}`}
                          className="w-full md:w-auto"
                        >
                          <button className="w-full md:w-auto bg-blue-600 text-white font-medium py-2 px-4 rounded-md text-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 dark:focus:ring-offset-slate-800 transition-colors">
                            View Results
                          </button>
                        </Link>

                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <button className="p-2 text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-slate-500 dark:focus:ring-offset-slate-800 transition-colors">
                              <Trash2 className="h-5 w-5" />
                            </button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>
                                Delete Session?
                              </AlertDialogTitle>
                              <AlertDialogDescription>
                                This will permanently delete the analysis
                                results for
                                <span className="font-semibold text-slate-900">
                                  {" "}
                                  {session.filename}
                                </span>
                                . This action cannot be undone.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleDelete(session.session_id)}
                                className="bg-red-600 hover:bg-red-700"
                              >
                                {deletingId === session.session_id
                                  ? "Deleting..."
                                  : "Delete"}
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </main>
        </div>
      </div>
    </LockScreen>
  );
}
