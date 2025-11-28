'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { FileCheck, AlertCircle, CheckSquare, Mail, Copy, Check } from 'lucide-react';
import { Separator } from '@/components/ui/separator';
import ReactMarkdown from 'react-markdown';
import { useState } from 'react';

interface NegotiationSummary {
  executive_summary?: string;
  priority_issues?: string[];
  checklist?: string[];
  draft_email?: string;
}

interface SummaryTabProps {
  data: Record<string, unknown>;
}

export default function SummaryTab({ data }: SummaryTabProps) {
  const results = (data?.results || {}) as Record<string, unknown>;
  const summaryData = (results?.summary || {}) as Record<string, unknown>;
  const summary = (summaryData?.negotiation_summary || (data as Record<string, unknown>)?.negotiation_summary || {}) as NegotiationSummary;
  
  const [copied, setCopied] = useState(false);

  // Parse subject line from email if it exists
  const parseEmail = (email: string) => {
    const subjectMatch = email.match(/^Subject:\s*(.+?)(?:\n|$)/i);
    if (subjectMatch) {
      const subject = subjectMatch[1].trim();
      const body = email.replace(/^Subject:\s*.+?(?:\n|$)/i, '').trim();
      return { subject, body };
    }
    return { subject: 'Contract Review and Discussion Points', body: email };
  };

  const emailData = summary.draft_email ? parseEmail(summary.draft_email) : null;

  const handleCopyEmail = () => {
    if (summary.draft_email && emailData) {
      // Format the email with To and Subject
      const emailContent = `To: [Counterparty Contact Name]\nSubject: ${emailData.subject}\n\n${emailData.body}`;
      navigator.clipboard.writeText(emailContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xl font-semibold mb-4">
          Negotiation Summary
        </h3>
      </div>

      {/* Executive Summary */}
      {summary.executive_summary && (
        <Card className="border-blue-200">
          <CardHeader className="bg-blue-50">
            <CardTitle className="text-lg flex items-center gap-2">
              <FileCheck className="w-5 h-5 text-blue-600" />
              Executive Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="prose prose-sm max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-strong:text-slate-900 prose-ul:text-slate-700">
              <ReactMarkdown>{summary.executive_summary}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Priority Issues */}
      {summary.priority_issues && Array.isArray(summary.priority_issues) && summary.priority_issues.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-amber-600" />
              Priority Issues
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {summary.priority_issues.map((issue, index) => (
              <Alert key={index} className="border-amber-200 bg-amber-50">
                <AlertDescription className="flex items-start gap-3">
                  <Badge variant="outline" className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center p-0 border-amber-500 text-amber-700">
                    {index + 1}
                  </Badge>
                  <div className="flex-1 prose prose-sm max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-strong:text-slate-900">
                    <ReactMarkdown>{issue}</ReactMarkdown>
                  </div>
                </AlertDescription>
              </Alert>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Negotiation Checklist */}
      {summary.checklist && Array.isArray(summary.checklist) && summary.checklist.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <CheckSquare className="w-5 h-5 text-green-600" />
              Negotiation Checklist
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {summary.checklist.map((item, index) => (
                <li key={index} className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    className="mt-1 w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm flex-1">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Draft Email */}
      {summary.draft_email && emailData && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mail className="w-5 h-5 text-blue-600" />
              Draft Negotiation Email
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="bg-muted/50 rounded-lg p-4 space-y-3">
              <div className="space-y-2 text-sm border-b border-border pb-3">
                <div className="flex gap-2">
                  <span className="font-semibold text-slate-900">To:</span>
                  <span className="text-slate-600">[Counterparty Contact Name]</span>
                </div>
                <div className="flex gap-2">
                  <span className="font-semibold text-slate-900">Subject:</span>
                  <span className="text-slate-600">{emailData.subject}</span>
                </div>
              </div>
              
              <div className="prose prose-sm max-w-none prose-headings:text-slate-900 prose-p:text-slate-700 prose-strong:text-slate-900 prose-ul:text-slate-700">
                <ReactMarkdown>{emailData.body}</ReactMarkdown>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button onClick={handleCopyEmail} className="gap-2">
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy to Clipboard
                  </>
                )}
              </Button>
              {copied && (
                <span className="text-sm text-green-600 font-medium">
                  Email copied successfully!
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {!summary.executive_summary &&
        !summary.priority_issues &&
        !summary.checklist &&
        !summary.draft_email && (
          <div className="text-center py-12">
            <FileCheck className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
            <p className="text-muted-foreground">
              No negotiation summary available
            </p>
          </div>
        )}
    </div>
  );
}
