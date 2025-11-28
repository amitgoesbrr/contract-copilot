'use client';

import { useEffect, useState } from 'react';
import { Progress } from '@/components/ui/progress';

const stages = [
  { name: 'Ingestion', description: 'Parsing contract document' },
  { name: 'Extraction', description: 'Identifying clauses' },
  { name: 'Risk Analysis', description: 'Evaluating risks' },
  { name: 'Redline Generation', description: 'Creating suggestions' },
  { name: 'Summary', description: 'Preparing negotiation materials' },
  { name: 'Audit', description: 'Compiling audit trail' },
];

export default function ProgressIndicator() {
  const [currentStage, setCurrentStage] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStage((prev) => (prev < stages.length - 1 ? prev + 1 : prev));
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const progressPercentage = ((currentStage + 1) / stages.length) * 100;

  return (
    <div className="w-full max-w-3xl mx-auto bg-white dark:bg-slate-800/50 shadow-sm rounded-lg border border-slate-200 dark:border-slate-700 p-4 sm:p-8 mt-8">
      <h2 className="text-center text-2xl font-bold text-slate-900 dark:text-white mb-8">
        Processing Contract
      </h2>
      <div className="space-y-8">
        <div className="space-y-6">
          {stages.map((stage, index) => (
            <div key={stage.name} className="flex items-center gap-4">
              <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center">
                {index < currentStage ? (
                  <span className="material-symbols-outlined text-green-500 text-3xl">check_circle</span>
                ) : index === currentStage ? (
                  <span className="material-symbols-outlined text-primary text-3xl animate-spin">progress_activity</span>
                ) : (
                  <span className="material-symbols-outlined text-slate-300 dark:text-slate-600 text-3xl">radio_button_unchecked</span>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className={`font-semibold text-lg ${index <= currentStage ? 'text-slate-900 dark:text-white' : 'text-slate-400 dark:text-slate-500'
                    }`}
                >
                  {stage.name}
                </p>
                <p
                  className={`text-sm ${index <= currentStage ? 'text-slate-600 dark:text-slate-400' : 'text-slate-400/60 dark:text-slate-600'
                    }`}
                >
                  {stage.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-3">
          <Progress value={progressPercentage} className="h-2 bg-slate-100 dark:bg-slate-800" indicatorClassName="bg-primary" />
          <p className="text-sm text-center text-slate-500 dark:text-slate-400 font-medium">
            {Math.round(progressPercentage)}% Complete
          </p>
        </div>
      </div>
    </div>
  );
}
