'use client';

import { Badge } from '@/components/ui/badge';
import { AlertTriangle, AlertCircle, CheckCircle, ShieldAlert } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Risk {
  clause_id?: string;
  severity: string;
  risk_type: string;
  explanation: string;
  llm_rationale?: string;
}

interface RisksTabProps {
  data: Record<string, unknown>;
}

export default function RisksTab({ data }: RisksTabProps) {
  const results = (data?.results || {}) as Record<string, unknown>;
  const riskScoring = (results?.risk_scoring || {}) as Record<string, unknown>;
  const risks = (riskScoring?.risk_assessments || (data as Record<string, unknown>)?.risk_assessments || []) as Risk[];

  const getSeverityIcon = (severity: string) => {
    const icons: Record<string, React.ReactElement> = {
      high: <AlertCircle className="w-5 h-5 text-red-500" />,
      medium: <AlertTriangle className="w-5 h-5 text-amber-500" />,
      low: <CheckCircle className="w-5 h-5 text-green-500" />,
    };
    return icons[severity.toLowerCase()] || <ShieldAlert className="w-5 h-5" />;
  };

  const getSeverityVariant = (severity: string): "default" | "secondary" | "destructive" | "outline" => {
    const variants: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
      high: 'destructive',
      medium: 'outline',
      low: 'secondary',
    };
    return variants[severity.toLowerCase()] || 'default';
  };

  const sortedRisks = [...risks].sort((a, b) => {
    const severityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
    return (
      severityOrder[a.severity.toLowerCase()] -
      severityOrder[b.severity.toLowerCase()]
    );
  });

  const riskCounts = risks.reduce(
    (acc: Record<string, number>, risk) => {
      const severity = risk.severity.toLowerCase();
      acc[severity] = (acc[severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="space-y-4">
      <h3 className="text-xl font-semibold">Risk Assessment</h3>


      {/* Risk Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Severity Distribution */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Severity Distribution</h4>
          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden flex">
              {riskCounts.high > 0 && (
                <div style={{ width: `${(riskCounts.high / risks.length) * 100}%` }} className="bg-red-500 h-full" />
              )}
              {riskCounts.medium > 0 && (
                <div style={{ width: `${(riskCounts.medium / risks.length) * 100}%` }} className="bg-amber-500 h-full" />
              )}
              {riskCounts.low > 0 && (
                <div style={{ width: `${(riskCounts.low / risks.length) * 100}%` }} className="bg-green-500 h-full" />
              )}
            </div>
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-red-500"></div>High ({riskCounts.high || 0})</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-amber-500"></div>Medium ({riskCounts.medium || 0})</span>
            <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-green-500"></div>Low ({riskCounts.low || 0})</span>
          </div>
        </div>

        {/* Top Risk Categories */}
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <h4 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-3">Top Risk Categories</h4>
          <div className="space-y-2">
            {Object.entries(risks.reduce((acc, r) => {
              acc[r.risk_type] = (acc[r.risk_type] || 0) + 1;
              return acc;
            }, {} as Record<string, number>))
              .sort(([, a], [, b]) => b - a)
              .slice(0, 3)
              .map(([type, count]) => (
                <div key={type} className="flex justify-between items-center text-sm">
                  <span className="truncate text-gray-700 dark:text-gray-300">{type}</span>
                  <Badge variant="secondary" className="ml-2">{count}</Badge>
                </div>
              ))}
          </div>
        </div>
      </div>

      {sortedRisks.length === 0 ? (
        <div className="text-center py-12">
          <ShieldAlert className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
          <p className="text-muted-foreground">No risks identified</p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedRisks.map((risk, index) => (
            <div
              key={risk.clause_id || index}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-5 transition-shadow hover:shadow-lg"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  {getSeverityIcon(risk.severity)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row justify-between items-start gap-2 mb-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {risk.risk_type}
                      </span>
                      <Badge variant={getSeverityVariant(risk.severity)} className="uppercase text-xs">
                        {risk.severity}
                      </Badge>
                    </div>
                    <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      Clause ID: {risk.clause_id}
                    </span>
                  </div>

                  <p className="text-sm mb-2 text-gray-600 dark:text-gray-300 leading-relaxed">
                    {risk.explanation}
                  </p>

                  {/* Show AI Analysis section only when available */}
                  {risk.llm_rationale && (
                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                      <p className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
                        AI Analysis:
                      </p>
                      <div className="text-xs text-gray-600 dark:text-gray-400 prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown
                          components={{
                            p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                            li: ({ children }) => <li className="ml-2">{children}</li>,
                            strong: ({ children }) => <strong className="font-semibold text-gray-800 dark:text-gray-200">{children}</strong>,
                            em: ({ children }) => <em className="italic">{children}</em>,
                            code: ({ children }) => <code className="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded text-xs">{children}</code>,
                          }}
                        >
                          {risk.llm_rationale}
                        </ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
