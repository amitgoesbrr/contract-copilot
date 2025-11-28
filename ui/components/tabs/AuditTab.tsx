'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Clock, Activity, BarChart3, AlertTriangle, Code } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface AgentTrace {
  agent_name?: string;
  latency_seconds?: number;
  duration?: number;
  success?: boolean;
  status?: string;
  input_hash?: string;
  output_hash?: string;
  error_message?: string | null;
}

interface AuditBundle {
  session_id?: string;
  timestamp?: string;
  created_at?: string;
  agent_traces?: AgentTrace[];
  extracted_clauses?: unknown[];
  risk_assessments?: unknown[];
  redline_proposals?: unknown[];
  disclaimer?: string;
}

interface AuditTabProps {
  data: Record<string, unknown>;
}

export default function AuditTab({ data }: AuditTabProps) {
  const results = (data?.results || {}) as Record<string, unknown>;
  const audit = (results?.audit || {}) as Record<string, unknown>;
  const auditBundle = (audit?.audit_bundle || (data as Record<string, unknown>)?.audit_bundle || data || {}) as AuditBundle;

  const formatTimestamp = (timestamp: string): string => {
    if (!timestamp) return 'N/A';
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="space-y-6" key="audit-tab">
      <div>
        <h3 className="text-xl font-semibold mb-2">
          Audit Trail
        </h3>
        <p className="text-sm text-muted-foreground">
          Complete traceable record of all analysis operations and AI decisions
        </p>
      </div>

      {/* Session Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Clock className="w-5 h-5" />
            Session Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="font-medium text-muted-foreground mb-1">Session ID:</dt>
              <dd className="font-mono text-xs bg-muted p-2 rounded">
                {auditBundle.session_id || 'N/A'}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-muted-foreground mb-1">Timestamp:</dt>
              <dd className="font-medium">
                {formatTimestamp((auditBundle.timestamp || auditBundle.created_at) as string)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Agent Traces */}
      {auditBundle.agent_traces && Array.isArray(auditBundle.agent_traces) && auditBundle.agent_traces.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Activity className="w-5 h-5" />
              Agent Execution Traces
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {auditBundle.agent_traces.map((trace, index) => {
              const duration = trace.latency_seconds || trace.duration;
              const isSuccess = trace.success !== undefined ? trace.success : trace.status === 'success';
              
              return (
                <Card key={index} className="bg-muted/50">
                  <CardContent className="p-4">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-semibold">
                        {trace.agent_name || `Agent ${index + 1}`}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {duration ? `${duration.toFixed(2)}s` : 'N/A'}
                      </Badge>
                    </div>
                    <Badge
                      variant={isSuccess ? 'default' : 'destructive'}
                      className="mb-2"
                    >
                      {isSuccess ? 'Success' : 'Failed'}
                    </Badge>
                    {trace.error_message && (
                      <Alert variant="destructive" className="mt-2 mb-2">
                        <AlertDescription className="text-xs">
                          {trace.error_message}
                        </AlertDescription>
                      </Alert>
                    )}
                    {trace.input_hash && (
                      <p className="text-xs text-muted-foreground mb-1">
                        Input Hash: <code className="font-mono bg-muted px-1 py-0.5 rounded">{trace.input_hash}</code>
                      </p>
                    )}
                    {trace.output_hash && (
                      <p className="text-xs text-muted-foreground">
                        Output Hash: <code className="font-mono bg-muted px-1 py-0.5 rounded">{trace.output_hash}</code>
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Statistics */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-600" />
            Analysis Statistics
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-background rounded-lg">
              <dt className="text-sm font-medium text-muted-foreground mb-2">Clauses Extracted</dt>
              <dd className="text-3xl font-bold text-blue-600">
                {Array.isArray(auditBundle.extracted_clauses) ? auditBundle.extracted_clauses.length : 0}
              </dd>
            </div>
            <div className="text-center p-4 bg-background rounded-lg">
              <dt className="text-sm font-medium text-muted-foreground mb-2">Risks Identified</dt>
              <dd className="text-3xl font-bold text-amber-600">
                {Array.isArray(auditBundle.risk_assessments) ? auditBundle.risk_assessments.length : 0}
              </dd>
            </div>
            <div className="text-center p-4 bg-background rounded-lg">
              <dt className="text-sm font-medium text-muted-foreground mb-2">Redlines Suggested</dt>
              <dd className="text-3xl font-bold text-green-600">
                {Array.isArray(auditBundle.redline_proposals) ? auditBundle.redline_proposals.length : 0}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* Disclaimer */}
      {auditBundle.disclaimer && (
        <Alert className="border-amber-200 bg-amber-50">
          <AlertTriangle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="ml-2">
            <p className="text-sm font-semibold mb-1">Disclaimer</p>
            <p className="text-xs">{auditBundle.disclaimer}</p>
          </AlertDescription>
        </Alert>
      )}

      {/* Raw Data Export */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Code className="w-5 h-5" />
            Raw Audit Data
          </CardTitle>
          <CardDescription>
            View the complete JSON audit bundle
          </CardDescription>
        </CardHeader>
        <CardContent>
          <details className="cursor-pointer group">
            <summary className="text-sm font-medium hover:text-primary transition-colors">
              Click to expand JSON data
            </summary>
            <ScrollArea className="h-96 w-full mt-3">
              <pre className="p-4 bg-slate-950 text-green-400 rounded-lg text-xs overflow-x-auto">
                {JSON.stringify(auditBundle, null, 2)}
              </pre>
            </ScrollArea>
          </details>
        </CardContent>
      </Card>
    </div>
  );
}
