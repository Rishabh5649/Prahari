import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import StatusBadge from './StatusBadge';
import ConfidencePill from './ConfidencePill';

export default function MapCard({ mapItem }) {
  const formattedDeadline = mapItem.deadline
    ? new Date(mapItem.deadline).toLocaleDateString()
    : 'No deadline';

  return (
    <Card className="border border-zinc-200 shadow-sm rounded-md bg-white">
      <CardHeader className="p-4 pb-2 flex flex-row items-start justify-between space-y-0">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
            {mapItem.department}
          </span>
          <CardTitle className="text-sm font-semibold text-zinc-900 leading-snug">
            {mapItem.what}
          </CardTitle>
        </div>
        <div className="flex flex-col items-end gap-1.5 ml-4">
          <StatusBadge status={mapItem.status} />
          <ConfidencePill score={mapItem.confidence_score} />
        </div>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="flex justify-between items-center text-xs text-zinc-500 mt-2">
          <span>Deadline: {formattedDeadline}</span>
          {mapItem.confidence_score !== undefined && (
            <span>Confidence: {(mapItem.confidence_score * 100).toFixed(0)}%</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
