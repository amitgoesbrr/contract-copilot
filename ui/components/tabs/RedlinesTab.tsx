'use client';

import DiffViewer from '../DiffViewer';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Edit3, Lightbulb } from 'lucide-react';

interface Redline {
  clause_id?: string;
  rationale: string;
  original_text: string;
  proposed_text: string;
  diff?: string;
}

interface RedlinesTabProps {
  data: Record<string, unknown>;
}

export default function RedlinesTab({ data }: RedlinesTabProps) {
  const results = (data?.results || {}) as Record<string, unknown>;
  const redline = (results?.redline || {}) as Record<string, unknown>;
  const redlines = (redline?.redline_proposals || (data as Record<string, unknown>)?.redline_proposals || []) as Redline[];

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-xl font-semibold">
          Redline Suggestions
        </h3>
        <Badge variant="secondary" className="text-sm">
          {redlines.length} suggestion{redlines.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      {redlines.length === 0 ? (
        <div className="text-center py-12">
          <Edit3 className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
          <p className="text-muted-foreground">
            No redline suggestions generated
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {redlines.map((redline, index) => (
            <Card
              key={redline.clause_id || index}
              className="overflow-hidden"
            >
              <CardHeader className="bg-muted/50">
                <div className="flex justify-between items-center">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Edit3 className="w-4 h-4" />
                    Redline {index + 1}
                  </CardTitle>
                  <Badge variant="outline" className="text-xs">
                    Clause ID: {redline.clause_id}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent className="p-4 space-y-4">
                <Alert className="border-blue-200 bg-blue-50">
                  <Lightbulb className="h-4 w-4 text-blue-600" />
                  <AlertDescription className="ml-2">
                    <p className="text-sm font-medium mb-1">Rationale:</p>
                    <p className="text-sm">{redline.rationale}</p>
                  </AlertDescription>
                </Alert>

                <DiffViewer
                  original={redline.original_text}
                  proposed={redline.proposed_text}
                  diff={redline.diff}
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
