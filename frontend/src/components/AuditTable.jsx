import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export default function AuditTable({ logs }) {
  const [expandedRow, setExpandedRow] = useState(null);

  const toggleExpand = (id) => {
    if (expandedRow === id) {
      setExpandedRow(null);
    } else {
      setExpandedRow(id);
    }
  };

  if (!logs || logs.length === 0) {
    return <div className="text-sm text-zinc-500 py-4 text-center">No audit logs found.</div>;
  }

  return (
    <div className="border border-zinc-200 rounded-md overflow-hidden bg-white">
      <Table>
        <TableHeader className="bg-zinc-50">
          <TableRow>
            <TableHead className="font-semibold text-xs text-zinc-700">Event Type</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700">Entity Type</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700">Entity ID</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700">Actor</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700">Model Version</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700">Created At</TableHead>
            <TableHead className="font-semibold text-xs text-zinc-700 text-right">Payload</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => {
            const isExpanded = expandedRow === log.id;
            return (
              <React.Fragment key={log.id}>
                <TableRow className="hover:bg-zinc-50/50 cursor-pointer" onClick={() => toggleExpand(log.id)}>
                  <TableCell className="font-medium text-xs text-zinc-900">{log.event_type}</TableCell>
                  <TableCell className="text-xs text-zinc-500 capitalize">{log.entity_type}</TableCell>
                  <TableCell className="text-xs font-mono text-zinc-500 max-w-[120px] truncate" title={log.entity_id}>
                    {log.entity_id}
                  </TableCell>
                  <TableCell className="text-xs text-zinc-700">{log.actor || 'system'}</TableCell>
                  <TableCell className="text-xs font-mono text-zinc-500">{log.model_version || '—'}</TableCell>
                  <TableCell className="text-xs text-zinc-500">
                    {new Date(log.created_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-xs text-zinc-700 text-right font-medium">
                    <button
                      type="button"
                      className="text-zinc-600 hover:text-zinc-900 underline text-xs font-semibold focus:outline-none"
                    >
                      {isExpanded ? 'Hide' : 'Show'}
                    </button>
                  </TableCell>
                </TableRow>
                {isExpanded && (
                  <TableRow className="bg-zinc-50/30">
                    <TableCell colSpan={7} className="p-4 border-t border-zinc-200">
                      <div className="bg-zinc-900 text-zinc-200 font-mono text-[11px] p-3 rounded overflow-auto max-h-[300px] text-left leading-relaxed">
                        <pre>{JSON.stringify(log.payload, null, 2)}</pre>
                      </div>
                      {(log.input_hash || log.output_hash) && (
                        <div className="mt-2 flex flex-col gap-1 text-[11px] text-zinc-500 font-mono text-left">
                          {log.input_hash && <div>Input Hash: {log.input_hash}</div>}
                          {log.output_hash && <div>Output Hash: {log.output_hash}</div>}
                        </div>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
