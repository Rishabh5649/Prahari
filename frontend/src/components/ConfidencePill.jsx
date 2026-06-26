import React from 'react';

export default function ConfidencePill({ score }) {
  if (score === undefined || score === null) return null;
  if (score < 0.7) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-orange-100 text-orange-800 border border-orange-200 whitespace-nowrap">
        ⚠️ Low confidence
      </span>
    );
  }
  return null;
}
