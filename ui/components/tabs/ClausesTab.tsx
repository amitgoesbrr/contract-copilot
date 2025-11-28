'use client';

import { FileText } from 'lucide-react';

interface Clause {
  id?: string;
  type: string;
  text: string;
  page_number?: number;
  start_line?: number;
  end_line?: number;
}

interface ClausesTabProps {
  data: Record<string, unknown>;
}

export default function ClausesTab({ data }: ClausesTabProps) {
  const results = (data?.results || {}) as Record<string, unknown>;
  const extraction = (results?.extraction || {}) as Record<string, unknown>;
  const clauses = (extraction?.clauses || (data as Record<string, unknown>)?.extracted_clauses || []) as Clause[];

  // Format clause type: "payment_terms" -> "Payment Terms"
  const formatClauseType = (type: string): string => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  // Get color classes for clause type badges
  const getClauseTypeColor = (type: string): string => {
    const normalizedType = type.toLowerCase().replace(/_/g, ' ');
    const colors: Record<string, string> = {
      'payment terms': 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
      'liability': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
      'other': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200',
      'confidentiality': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
      'termination': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
      'indemnification': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
      'governing law': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
      'warranty': 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
      'intellectual property': 'bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200',
    };
    return colors[normalizedType] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Extracted Clauses
        </h3>
        <span className="text-sm font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 px-3 py-1 rounded-full">
          {clauses.length} clause{clauses.length !== 1 ? 's' : ''} found
        </span>
      </div>

      {clauses.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 mx-auto text-gray-400 mb-3" />
          <p className="text-gray-500 dark:text-gray-400">No clauses extracted</p>
        </div>
      ) : (
        <div className="space-y-4">
          {clauses.map((clause, index) => (
            <div
              key={clause.id || index}
              className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-5 transition-shadow hover:shadow-lg"
            >
              <div className="flex flex-col sm:flex-row justify-between sm:items-center mb-3">
                <div className="flex items-center gap-3 mb-2 sm:mb-0">
                  <h4 className="text-base font-semibold text-gray-800 dark:text-gray-100">
                    Clause {index + 1}
                  </h4>
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getClauseTypeColor(clause.type)}`}>
                    {formatClauseType(clause.type)}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Page {clause.page_number || 'N/A'} • Lines {clause.start_line}-{clause.end_line}
                </p>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed whitespace-pre-wrap">
                {clause.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
