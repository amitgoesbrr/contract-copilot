'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Columns2, List } from 'lucide-react';

interface DiffViewerProps {
  original: string;
  proposed: string;
  diff?: string;
}

export default function DiffViewer({
  original,
  proposed,
  diff,
}: DiffViewerProps) {
  const [viewMode, setViewMode] = useState<'split' | 'unified'>('split');

  const parseDiff = (diffText: string) => {
    if (!diffText) return [];
    const lines = diffText.split('\n');
    return lines.map((line) => {
      if (line.startsWith('+') && !line.startsWith('+++')) {
        return { type: 'added', content: line.substring(1) };
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        return { type: 'removed', content: line.substring(1) };
      } else if (line.startsWith('@@')) {
        return { type: 'info', content: line };
      } else {
        return { type: 'unchanged', content: line };
      }
    });
  };

  const diffLines = diff ? parseDiff(diff) : [];

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-sm font-medium">Changes:</h4>
        <div className="flex gap-2">
          <Button
            onClick={() => setViewMode('split')}
            variant={viewMode === 'split' ? 'default' : 'outline'}
            size="sm"
            className="gap-2"
          >
            <Columns2 className="w-3 h-3" />
            Split
          </Button>
          <Button
            onClick={() => setViewMode('unified')}
            variant={viewMode === 'unified' ? 'default' : 'outline'}
            size="sm"
            className="gap-2"
          >
            <List className="w-3 h-3" />
            Unified
          </Button>
        </div>
      </div>

      {viewMode === 'split' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Card className="border-red-200">
            <CardContent className="p-0">
              <div className="bg-red-50 px-3 py-2 border-b border-red-200">
                <Badge variant="outline" className="text-xs border-red-300 text-red-700">
                  Original
                </Badge>
              </div>
              <div className="bg-red-50/50 p-3 text-sm font-mono whitespace-pre-wrap max-h-96 overflow-auto">
                {original}
              </div>
            </CardContent>
          </Card>
          <Card className="border-green-200">
            <CardContent className="p-0">
              <div className="bg-green-50 px-3 py-2 border-b border-green-200">
                <Badge variant="outline" className="text-xs border-green-300 text-green-700">
                  Proposed
                </Badge>
              </div>
              <div className="bg-green-50/50 p-3 text-sm font-mono whitespace-pre-wrap max-h-96 overflow-auto">
                {proposed}
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardContent className="p-0">
            {diffLines.length > 0 ? (
              <div className="font-mono text-sm max-h-96 overflow-auto">
                {diffLines.map((line, index) => (
                  <div
                    key={index}
                    className={`px-3 py-1 ${
                      line.type === 'added'
                        ? 'bg-green-50 text-green-800'
                        : line.type === 'removed'
                        ? 'bg-red-50 text-red-800'
                        : line.type === 'info'
                        ? 'bg-blue-50 text-blue-800'
                        : 'bg-background text-muted-foreground'
                    }`}
                  >
                    <span className="select-none mr-2 text-muted-foreground/50">
                      {line.type === 'added'
                        ? '+'
                        : line.type === 'removed'
                        ? '-'
                        : ' '}
                    </span>
                    {line.content}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-sm text-muted-foreground text-center">
                No diff available. See split view for comparison.
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
