import React from 'react';
import { Badge } from '@/components/ui/badge';

export default function StatusBadge({ status }) {
  const normalized = status ? status.toLowerCase() : '';

  let colorClasses = 'bg-zinc-100 text-zinc-800 border-zinc-200'; // Default gray

  if (normalized === 'compliant' || normalized === 'satisfied') {
    colorClasses = 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-50';
  } else if (normalized === 'overdue' || normalized === 'insufficient') {
    colorClasses = 'bg-red-50 text-red-700 border-red-200 hover:bg-red-50';
  } else if (
    normalized === 'in_progress' ||
    normalized === 'assigned' ||
    normalized === 'evidence_submitted' ||
    normalized === 'judging' ||
    normalized === 'under_review'
  ) {
    colorClasses = 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-50';
  } else if (normalized === 'partial') {
    colorClasses = 'bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-50';
  } else if (normalized === 'pending_review' || normalized === 'processing') {
    colorClasses = 'bg-zinc-100 text-zinc-700 border-zinc-200 hover:bg-zinc-100';
  }

  // Format display text
  const displayText = status
    ? status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    : 'Unknown';

  return (
    <Badge variant="outline" className={`${colorClasses} font-medium px-2 py-0.5 rounded text-xs inline-block text-center whitespace-nowrap`}>
      {displayText}
    </Badge>
  );
}
