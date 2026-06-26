import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { getAuditLogs } from '@/api/audit';

const BASE_URL = 'http://localhost:8000';
const PAGE_SIZE = 50;

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };
  return (
    <button
      type="button"
      onClick={handleCopy}
      title="Copy full ID"
      className="ml-1 inline-flex items-center text-zinc-400 hover:text-zinc-700 focus:outline-none"
    >
      {copied ? (
        <svg className="w-3.5 h-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

function formatTimestamp(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())} ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())} UTC`;
}

export default function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialEntityId = searchParams.get('entity_id') || '';

  // Filter states
  const [entityType, setEntityType] = useState('');
  const [eventType, setEventType] = useState('');
  const [entityId, setEntityId] = useState(initialEntityId);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [page, setPage] = useState(1);

  // Data states
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedRow, setExpandedRow] = useState(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (entityType) params.entity_type = entityType;
      if (eventType) params.event_type = eventType;
      if (entityId) params.entity_id = entityId;
      const result = await getAuditLogs(params);
      setData(result);
    } catch {
      setError('Failed to retrieve audit log trail.');
    } finally {
      setLoading(false);
    }
  }, [page, entityType, eventType, entityId]);

  useEffect(() => {
    fetchLogs();
  }, [page]);

  const handleApplyFilters = (e) => {
    e.preventDefault();
    setPage(1);
    const params = {};
    if (entityId) params.entity_id = entityId;
    setSearchParams(params);
    fetchLogs();
  };

  const handleReset = () => {
    setEntityType('');
    setEventType('');
    setEntityId('');
    setFromDate('');
    setToDate('');
    setPage(1);
    setSearchParams({});
  };

  const handleExportCsv = () => {
    const queryParts = [];
    if (entityType) queryParts.push(`entity_type=${encodeURIComponent(entityType)}`);
    if (eventType) queryParts.push(`event_type=${encodeURIComponent(eventType)}`);
    if (entityId) queryParts.push(`entity_id=${encodeURIComponent(entityId)}`);
    let exportUrl = `${BASE_URL}/api/audit/export`;
    if (queryParts.length > 0) exportUrl += `?${queryParts.join('&')}`;
    window.open(exportUrl, '_blank');
  };

  const toggleRow = (id) => {
    setExpandedRow(expandedRow === id ? null : id);
  };

  const logs = data?.items || [];
  const totalPages = data?.total_pages || 1;
  const totalLogs = data?.total || 0;

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-6 px-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-left">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">System Audit Trail</h1>
          <p className="text-sm text-zinc-500">
            Immutable append-only logs tracking ingestion hashes, agent extractions, auditor verdicts, and human overrides.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={handleExportCsv}
          className="text-xs font-semibold px-3 py-1.5 h-auto rounded border-zinc-200 hover:bg-zinc-100"
        >
          Export CSV
        </Button>
      </div>

      {/* Horizontal Filter Bar */}
      <Card className="border border-zinc-200 shadow-sm bg-white text-left">
        <CardContent className="p-4">
          <form onSubmit={handleApplyFilters} className="flex flex-wrap items-end gap-3">
            <div className="space-y-1 min-w-[140px]">
              <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Entity Type</label>
              <select
                value={entityType}
                onChange={(e) => setEntityType(e.target.value)}
                className="w-full text-xs rounded border border-zinc-200 h-9 px-2 bg-white focus:outline-none focus:ring-1 focus:ring-zinc-950"
              >
                <option value="">All</option>
                <option value="circular">Circular</option>
                <option value="map_item">MAP Item</option>
                <option value="evidence">Evidence</option>
                <option value="judgment">Judgment</option>
              </select>
            </div>

            <div className="space-y-1 min-w-[180px]">
              <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Event Type</label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full text-xs rounded border border-zinc-200 h-9 px-2 bg-white focus:outline-none focus:ring-1 focus:ring-zinc-950"
              >
                <option value="">All</option>
                <option value="circular_ingested">Circular Ingested</option>
                <option value="map_extracted">MAP Extracted</option>
                <option value="map_routed">MAP Routed</option>
                <option value="evidence_submitted">Evidence Submitted</option>
                <option value="judgment_made">Judgment Made</option>
                <option value="human_override">Human Override</option>
                <option value="map_escalated_overdue">MAP Escalated Overdue</option>
              </select>
            </div>

            <div className="space-y-1 min-w-[110px]">
              <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">From Date</label>
              <Input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="text-xs rounded border-zinc-200 h-9 bg-white"
              />
            </div>

            <div className="space-y-1 min-w-[110px]">
              <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">To Date</label>
              <Input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="text-xs rounded border-zinc-200 h-9 bg-white"
              />
            </div>

            <div className="space-y-1 min-w-[200px] flex-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Entity ID</label>
              <Input
                type="text"
                placeholder="Paste UUID..."
                value={entityId}
                onChange={(e) => setEntityId(e.target.value)}
                className="text-xs rounded border-zinc-200 h-9 bg-white font-mono"
              />
            </div>

            <div className="flex gap-2 self-end">
              <Button
                type="submit"
                className="bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-1.5 h-9 px-4 rounded"
              >
                Apply Filters
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleReset}
                className="text-xs font-semibold border-zinc-200 hover:bg-zinc-100 py-1.5 h-9 px-3 rounded"
              >
                Reset
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Errors */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md text-xs font-medium text-left">
          {error}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col items-center justify-center min-h-[250px] gap-3">
          <div className="w-8 h-8 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm font-medium text-zinc-500">Loading audit trail...</p>
        </div>
      ) : logs.length === 0 ? (
        <div className="border border-dashed border-zinc-200 rounded-md p-8 text-center bg-zinc-50/50">
          <p className="text-sm text-zinc-500 font-medium">No audit logs match the current filters.</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="border border-zinc-200 rounded-md overflow-hidden bg-white">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow>
                  <TableHead className="font-semibold text-xs text-zinc-700">Timestamp</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Event</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Entity Type</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Entity ID</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Actor</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Model Version</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => {
                  const isExpanded = expandedRow === log.id;
                  const truncatedId = log.entity_id
                    ? `${log.entity_id.slice(0, 8)}...`
                    : '—';

                  return (
                    <React.Fragment key={log.id}>
                      <TableRow
                        className="hover:bg-zinc-50/50 cursor-pointer"
                        onClick={() => toggleRow(log.id)}
                      >
                        <TableCell className="text-xs font-mono text-zinc-600 whitespace-nowrap">
                          {formatTimestamp(log.created_at)}
                        </TableCell>
                        <TableCell className="text-xs font-medium text-zinc-900">
                          {log.event_type}
                        </TableCell>
                        <TableCell className="text-xs text-zinc-500 capitalize">
                          {log.entity_type}
                        </TableCell>
                        <TableCell className="text-xs font-mono text-zinc-500">
                          <span title={log.entity_id}>{truncatedId}</span>
                          {log.entity_id && <CopyButton text={log.entity_id} />}
                        </TableCell>
                        <TableCell className="text-xs text-zinc-700">
                          {log.actor || 'system'}
                        </TableCell>
                        <TableCell className="text-xs font-mono text-zinc-500">
                          {log.model_version || '—'}
                        </TableCell>
                      </TableRow>

                      {isExpanded && (
                        <TableRow className="bg-zinc-50/30">
                          <TableCell colSpan={6} className="p-4 border-t border-zinc-200">
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

          {/* Pagination */}
          <div className="flex items-center justify-between py-2 border-t border-zinc-200">
            <span className="text-xs text-zinc-500">
              Page <strong className="font-semibold text-zinc-950">{page}</strong> of{' '}
              <strong className="font-semibold text-zinc-950">{totalPages}</strong>{' '}
              ({totalLogs} total logs)
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="text-xs font-semibold px-3 py-1 h-8 rounded border-zinc-200 hover:bg-zinc-100"
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="text-xs font-semibold px-3 py-1 h-8 rounded border-zinc-200 hover:bg-zinc-100"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
