'use client';

import { useState } from 'react';
import ClausesTab from './tabs/ClausesTab';
import RisksTab from './tabs/RisksTab';
import RedlinesTab from './tabs/RedlinesTab';
import SummaryTab from './tabs/SummaryTab';
import AuditTab from './tabs/AuditTab';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface ResultsDisplayProps {
  results: Record<string, unknown>;
  sessionId: string | null;
  onReset: () => void;
}

const tabs = [
  { id: 'clauses', name: 'Clauses', icon: 'description' },
  { id: 'risks', name: 'Risks', icon: 'warning' },
  { id: 'redlines', name: 'Redlines', icon: 'edit_document' },
  { id: 'summary', name: 'Summary', icon: 'summarize' },
  { id: 'audit', name: 'Audit Trail', icon: 'history' },
];

export default function ResultsDisplay({
  results,
  sessionId,
  onReset,
}: ResultsDisplayProps) {
  const [activeTab, setActiveTab] = useState('clauses');

  const handleDownloadJSON = () => {
    const dataStr = JSON.stringify(results, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `contract-audit-${sessionId}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadMarkdown = async () => {
    try {
      const response = await fetch(`/api/results/${sessionId}/markdown`, {
        credentials: 'include',
      });
      if (!response.ok) {
        // Fallback: generate markdown on client side
        const markdown = generateMarkdown(results);
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `contract-audit-${sessionId}.md`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        const markdown = await response.text();
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `contract-audit-${sessionId}.md`;
        link.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Failed to download markdown:', error);
    }
  };

  const generateMarkdown = (data: Record<string, unknown>): string => {
    const res = (data?.results || {}) as Record<string, unknown>;
    const extraction = (res?.extraction || {}) as Record<string, unknown>;
    const riskScoring = (res?.risk_scoring || {}) as Record<string, unknown>;
    const summary = (res?.summary || {}) as Record<string, unknown>;
    const negotiationSummary = (summary?.negotiation_summary || {}) as Record<string, unknown>;

    let md = `# Contract Analysis Report\n\n`;
    md += `**Session ID:** ${sessionId}\n\n`;
    md += `**Generated:** ${new Date().toLocaleString()}\n\n`;
    md += `---\n\n`;

    // Executive Summary
    if (negotiationSummary.executive_summary) {
      md += `## Executive Summary\n\n${negotiationSummary.executive_summary}\n\n`;
    }

    // Clauses
    const clauses = (extraction?.clauses || []) as Array<Record<string, unknown>>;
    if (clauses.length > 0) {
      md += `## Extracted Clauses (${clauses.length})\n\n`;
      clauses.forEach((clause, i) => {
        md += `### ${i + 1}. ${clause.type}\n\n`;
        md += `${clause.text}\n\n`;
      });
    }

    // Risks
    const risks = (riskScoring?.risk_assessments || []) as Array<Record<string, unknown>>;
    if (risks.length > 0) {
      md += `## Risk Assessments\n\n`;
      risks.forEach((risk) => {
        md += `### ${risk.clause_id} - ${risk.severity?.toString().toUpperCase()}\n\n`;
        md += `**Risk Type:** ${risk.risk_type}\n\n`;
        md += `**Explanation:** ${risk.explanation}\n\n`;
        if (risk.llm_rationale) {
          md += `**AI Analysis:**\n\n${risk.llm_rationale}\n\n`;
        }
      });
    }

    return md;
  };

  return (
    <div className="bg-white dark:bg-slate-800/50 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700">
      <div className="flex flex-col sm:flex-row items-center justify-between p-4 sm:p-6 border-b border-slate-200 dark:border-slate-700">
        <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white mb-4 sm:mb-0">
          Analysis Results
        </h2>
        <div className="flex items-center space-x-2 sm:space-x-3">
          <Button
            onClick={onReset}
            size="sm"
            className="gap-2 bg-primary hover:bg-indigo-700 text-white"
          >
            <span className="material-symbols-outlined text-lg">restart_alt</span>
            <span className="hidden sm:inline">New Analysis</span>
            <span className="sm:hidden">New</span>
          </Button>
        </div>
      </div>

      <div className="border-b border-slate-200 dark:border-slate-700">
        <nav className="-mb-px flex flex-wrap" aria-label="Tabs">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`group inline-flex items-center gap-2 py-4 px-4 sm:px-6 border-b-2 font-medium text-sm transition-colors ${isActive
                  ? 'border-primary text-primary'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600'
                  }`}
                aria-current={isActive ? 'page' : undefined}
              >
                <span className={`material-symbols-outlined text-lg ${isActive ? 'text-primary' : 'text-slate-400 group-hover:text-slate-500'}`}>
                  {tab.icon}
                </span>
                <span className="hidden sm:inline">{tab.name}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="p-4 sm:p-6 bg-slate-50 dark:bg-slate-900/50 rounded-b-lg">
        {activeTab === 'clauses' && <ClausesTab data={results} />}
        {activeTab === 'risks' && <RisksTab data={results} />}
        {activeTab === 'redlines' && <RedlinesTab data={results} />}
        {activeTab === 'summary' && <SummaryTab data={results} />}
        {activeTab === 'audit' && <AuditTab data={results} />}
      </div>
    </div>
  );
}

