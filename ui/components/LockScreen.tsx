"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LockScreenProps {
  children: React.ReactNode;
}

export default function LockScreen({ children }: LockScreenProps) {
  const [isLocked, setIsLocked] = useState(true);
  const [accessCode, setAccessCode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const response = await fetch(`${API_URL}/verify`, {
        credentials: "include",
      });
      if (response.ok) {
        setIsLocked(false);
      }
    } catch (err) {
      console.error("Session check failed:", err);
    }
  };

  const handleUnlock = async () => {
    if (!accessCode.trim()) {
      setError("Please enter the access code");
      return;
    }

    try {
      const response = await fetch(`${API_URL}/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ access_code: accessCode }),
        credentials: "include",
      });

      if (response.ok) {
        setIsLocked(false);
      } else {
        setError("Invalid access code");
      }
    } catch (err) {
      console.error("Verification failed:", err);
      setError("Failed to verify code. Please ensure the backend is running.");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleUnlock();
    }
  };

  if (!isLocked) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-900 p-4">
      <div className="w-full max-w-md bg-white dark:bg-slate-800 rounded-lg shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white mb-2">
            Restricted Access
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Please enter the admin access code to continue.
          </p>
        </div>

        <div className="space-y-4">
          <div>
            <Input
              type="password"
              placeholder="Access Code"
              value={accessCode}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setAccessCode(e.target.value);
                setError("");
              }}
              onKeyDown={handleKeyDown}
              className="w-full"
            />
            {error && <p className="text-sm text-red-500 mt-1">{error}</p>}
          </div>

          <Button
            onClick={handleUnlock}
            className="w-full bg-primary hover:bg-indigo-700 text-white"
          >
            Unlock
          </Button>
        </div>
      </div>
    </div>
  );
}
