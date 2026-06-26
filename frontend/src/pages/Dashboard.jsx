import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import StatusBadge from '@/components/StatusBadge';
import ConfidencePill from '@/components/ConfidencePill';
import { getStats, getCirculars } from '@/api/dashboard';
import { getPendingReviewMaps, approveMap, rejectMap } from '@/api/maps';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [circulars, setCirculars] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Pending review queue
  const [pendingMaps, setPendingMaps] = useState([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [reviewActionLoading, setReviewActionLoading] = useState(null); // mapId being acted on
  const [reviewSuccess, setReviewSuccess] = useState(''); // inline confirmation
  const [rejectFormId, setRejectFormId] = useState(null); // which MAP shows reject form
  const [rejectReason, setRejectReason] = useState('');

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const [statsData, circularsData] = await Promise.all([getStats(), getCirculars()]);
      setStats(statsData);

      // Sort: overdue status first, then nearest deadline
      const sortedCirculars = [...circularsData].sort((a, b) => {
        if (a.status === 'overdue' && b.status !== 'overdue') return -1;
        if (a.status !== 'overdue' && b.status === 'overdue') return 1;

        if (a.days_to_nearest_deadline === null && b.days_to_nearest_deadline !== null) return 1;
        if (a.days_to_nearest_deadline !== null && b.days_to_nearest_deadline === null) return -1;
        if (a.days_to_nearest_deadline !== null && b.days_to_nearest_deadline !== null) {
          return a.days_to_nearest_deadline - b.days_to_nearest_deadline;
        }
        return new Date(b.ingested_at) - new Date(a.ingested_at);
      });

      setCirculars(sortedCirculars);
    } catch (err) {
      console.error(err);
      setError('Failed to load dashboard data. Please make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const fetchPendingMaps = async () => {
    setPendingLoading(true);
    try {
      const maps = await getPendingReviewMaps();
      setPendingMaps(maps);
    } catch {
      /* silently fail — section just stays empty */
    } finally {
      setPendingLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchPendingMaps();
  }, []);

  const handleApprove = async (mapId) => {
    setReviewActionLoading(mapId);
    setReviewSuccess('');
    try {
      await approveMap(mapId, 'Compliance Officer');
      setPendingMaps((prev) => prev.filter((m) => m.id !== mapId));
      setReviewSuccess(`MAP approved successfully.`);
      setTimeout(() => setReviewSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to approve MAP.');
    } finally {
      setReviewActionLoading(null);
    }
  };

  const handleReject = async (mapId) => {
    if (!rejectReason.trim()) return;
    setReviewActionLoading(mapId);
    setReviewSuccess('');
    try {
      await rejectMap(mapId, 'Compliance Officer', rejectReason);
      setPendingMaps((prev) => prev.filter((m) => m.id !== mapId));
      setRejectFormId(null);
      setRejectReason('');
      setReviewSuccess(`MAP rejected.`);
      setTimeout(() => setReviewSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reject MAP.');
    } finally {
      setReviewActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="w-8 h-8 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm font-medium text-zinc-600">Loading compliance stats...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4 text-center">
        <div className="bg-red-50 text-red-700 p-4 rounded-md border border-red-200 text-sm font-medium">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8 py-6 px-4">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">Compliance Workspace</h1>
        <p className="text-sm text-zinc-500">
          Executive dashboard monitoring active regulatory requirements and audit results.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Total Circulars
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-2xl font-bold text-zinc-900">{stats?.total_circulars ?? 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Compliant Circulars
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-2xl font-bold text-emerald-600">{stats?.compliant_circulars ?? 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Overdue Circulars
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-2xl font-bold text-red-600">{stats?.overdue_circulars ?? 0}</p>
          </CardContent>
        </Card>

        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4 pb-1">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-zinc-500">
              Pending Review MAPs
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-2xl font-bold text-zinc-800">{stats?.maps_pending_review ?? 0}</p>
          </CardContent>
        </Card>
      </div>

      {/* Circulars Table */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-zinc-900">Ingested Circulars</h2>
        {circulars.length === 0 ? (
          <div className="border border-dashed border-zinc-200 rounded-md p-8 text-center bg-zinc-50/50">
            <p className="text-sm text-zinc-500 font-medium">No circulars ingested yet.</p>
            <Link to="/ingest" className="inline-block mt-3">
              <Button size="sm" className="bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold px-4 py-1.5 h-auto rounded">
                Ingest First Circular
              </Button>
            </Link>
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-hidden bg-white">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow>
                  <TableHead className="font-semibold text-xs text-zinc-700">Title / URL</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Status</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700 text-center">Total MAPs</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700 text-center">Satisfied</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700 text-center">Overdue</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Nearest Deadline</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {circulars.map((c) => (
                  <TableRow key={c.id} className="hover:bg-zinc-50/30">
                    <TableCell className="max-w-[400px] min-w-[200px] whitespace-normal break-words pr-4">
                      <div className="flex flex-col gap-0.5">
                        <Link
                          to={`/circular/${c.id}`}
                          className="font-semibold text-xs text-zinc-950 hover:underline leading-relaxed line-clamp-2"
                        >
                          {c.title || 'Untitled Circular'}
                        </Link>
                        {c.source_url && (
                          <a
                            href={c.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-zinc-500 font-mono hover:underline truncate"
                          >
                            {c.source_url}
                          </a>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={c.status} />
                    </TableCell>
                    <TableCell className="text-center text-xs font-medium text-zinc-900">{c.total_maps}</TableCell>
                    <TableCell className="text-center text-xs font-medium text-emerald-600">{c.maps_satisfied}</TableCell>
                    <TableCell className="text-center text-xs font-medium text-red-600">{c.maps_overdue}</TableCell>
                    <TableCell className="text-xs text-zinc-700">
                      {c.days_to_nearest_deadline !== null ? (
                        c.days_to_nearest_deadline < 0 ? (
                          <span className="text-red-600 font-semibold">{Math.abs(c.days_to_nearest_deadline)} days ago</span>
                        ) : c.days_to_nearest_deadline === 0 ? (
                          <span className="text-amber-600 font-semibold">Today</span>
                        ) : (
                          <span>In {c.days_to_nearest_deadline} days</span>
                        )
                      ) : (
                        <span className="text-zinc-400">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <Link to={`/circular/${c.id}`}>
                        <Button
                          variant="outline"
                          className="text-xs font-semibold px-2.5 py-1 border-zinc-200 hover:bg-zinc-100 hover:text-zinc-900 h-auto rounded"
                        >
                          View
                        </Button>
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>

      {/* ──────────────────── Pending Human Review Queue ──────────────────── */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-zinc-900">
          Pending Human Review ({pendingMaps.length})
        </h2>

        {/* Inline success toast */}
        {reviewSuccess && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-md text-xs font-medium text-left">
            ✓ {reviewSuccess}
          </div>
        )}

        {pendingLoading ? (
          <div className="flex items-center gap-2 py-4">
            <div className="w-5 h-5 border-2 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
            <span className="text-xs text-zinc-500">Loading pending reviews...</span>
          </div>
        ) : pendingMaps.length === 0 ? (
          <div className="border border-dashed border-zinc-200 rounded-md p-6 text-center bg-zinc-50/50">
            <p className="text-sm text-zinc-500 font-medium">No MAPs pending human review.</p>
          </div>
        ) : (
          <div className="border border-zinc-200 rounded-md overflow-hidden bg-white">
            <Table>
              <TableHeader className="bg-zinc-50">
                <TableRow>
                  <TableHead className="font-semibold text-xs text-zinc-700">Requirement</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Circular</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700">Confidence</TableHead>
                  <TableHead className="font-semibold text-xs text-zinc-700 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingMaps.map((m) => (
                  <React.Fragment key={m.id}>
                    <TableRow className="hover:bg-zinc-50/50">
                      <TableCell className="max-w-[500px] min-w-[250px] whitespace-normal break-words pr-4 text-xs font-medium text-zinc-900 text-left">
                        {m.what}
                      </TableCell>
                      <TableCell className="text-xs text-zinc-500">
                        <Link
                          to={`/circular/${m.circular_id}`}
                          className="hover:underline text-zinc-700 font-medium"
                        >
                          {m.circular_id.slice(0, 8)}...
                        </Link>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-zinc-700">
                            {(m.confidence_score * 100).toFixed(0)}%
                          </span>
                          <ConfidencePill score={m.confidence_score} />
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            size="sm"
                            disabled={reviewActionLoading === m.id}
                            onClick={() => handleApprove(m.id)}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold px-3 py-1 h-7 rounded"
                          >
                            Approve
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={reviewActionLoading === m.id}
                            onClick={() => {
                              setRejectFormId(rejectFormId === m.id ? null : m.id);
                              setRejectReason('');
                            }}
                            className="text-[11px] font-semibold px-3 py-1 h-7 rounded border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                          >
                            Reject
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>

                    {/* Inline reject reason form */}
                    {rejectFormId === m.id && (
                      <TableRow className="bg-zinc-50/50">
                        <TableCell colSpan={4} className="p-4 border-t border-zinc-200 whitespace-normal">
                          <div className="flex items-end gap-3 max-w-xl text-left">
                            <div className="flex-1 space-y-1.5">
                              <label className="text-xs font-bold text-zinc-700">Rejection Reason</label>
                              <Input
                                type="text"
                                placeholder="Why is this extraction incorrect?"
                                value={rejectReason}
                                onChange={(e) => setRejectReason(e.target.value)}
                                disabled={reviewActionLoading === m.id}
                                className="text-xs rounded border-zinc-200 h-9 bg-white"
                                required
                              />
                            </div>
                            <Button
                              size="sm"
                              disabled={reviewActionLoading === m.id || !rejectReason.trim()}
                              onClick={() => handleReject(m.id)}
                              className="bg-red-600 hover:bg-red-700 text-white text-xs font-semibold px-4 py-1.5 h-9 rounded"
                            >
                              Confirm Reject
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={reviewActionLoading === m.id}
                              onClick={() => {
                                setRejectFormId(null);
                                setRejectReason('');
                              }}
                              className="text-xs font-semibold border-zinc-200 hover:bg-zinc-100 py-1.5 h-9 px-3 rounded bg-white"
                            >
                              Cancel
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
}
