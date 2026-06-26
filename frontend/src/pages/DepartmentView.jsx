import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
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
import { getDepartmentMaps } from '@/api/dashboard';
import { submitEvidence } from '@/api/evidence';
import { judgeEvidence, overrideJudgment } from '@/api/judgments';

export default function DepartmentView() {
  const { dept } = useParams();
  const [maps, setMaps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // UI States
  const [activeEvidenceForm, setActiveEvidenceForm] = useState(null); // mapId
  const [activeOverrideForm, setActiveOverrideForm] = useState(null); // mapId
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');

  // Form States
  const [evidenceFile, setEvidenceFile] = useState(null);
  const [submittedBy, setSubmittedBy] = useState('');
  const [overrideVerdict, setOverrideVerdict] = useState('satisfied');
  const [overrideBy, setOverrideBy] = useState('');
  const [overrideReason, setOverrideReason] = useState('');

  const fetchMaps = async () => {
    try {
      setLoading(true);
      const data = await getDepartmentMaps(dept);
      setMaps(data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to load department MAPs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMaps();
  }, [dept]);

  const handleEvidenceSubmit = async (e, mapId) => {
    e.preventDefault();
    if (!evidenceFile || !submittedBy) return;
    setActionLoading(true);
    setActionError('');
    try {
      // 1. Submit evidence
      const response = await submitEvidence(mapId, evidenceFile, submittedBy);
      
      // 2. Auto-trigger judgment
      if (response && response.id) {
        await judgeEvidence(mapId, response.id);
      }

      // Reset states and refresh
      setEvidenceFile(null);
      setSubmittedBy('');
      setActiveEvidenceForm(null);
      await fetchMaps();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to submit evidence and run judgment.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleJudgeTrigger = async (mapId, evidence) => {
    if (!evidence) return;
    setActionLoading(true);
    setActionError('');
    try {
      await judgeEvidence(mapId, evidence.id || evidence.evidence_id);
      await fetchMaps();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to run judge agent.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleOverrideSubmit = async (e, judgment) => {
    e.preventDefault();
    if (!overrideBy || !overrideReason) return;
    setActionLoading(true);
    setActionError('');
    try {
      await overrideJudgment(judgment.id, {
        newVerdict: overrideVerdict,
        overrideBy,
        overrideReason,
      });
      // Reset states and refresh
      setOverrideBy('');
      setOverrideReason('');
      setActiveOverrideForm(null);
      await fetchMaps();
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Failed to submit override judgment.');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-3">
        <div className="w-8 h-8 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-sm font-medium text-zinc-600">Loading department workspace...</p>
      </div>
    );
  }

  const openMapsCount = maps.filter((m) => m.status !== 'satisfied').length;

  return (
    <div className="max-w-6xl mx-auto space-y-6 py-6 px-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 text-left">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">
            {dept} Department
          </h1>
          <p className="text-sm text-zinc-500 font-medium">
            Currently tracking <strong className="font-semibold text-zinc-900">{openMapsCount}</strong> open compliance requirements.
          </p>
        </div>
        <div>
          <Link to="/">
            <Button variant="outline" className="text-xs font-semibold px-3 py-1.5 h-auto rounded border-zinc-200 hover:bg-zinc-100">
              ← Workspace Home
            </Button>
          </Link>
        </div>
      </div>

      {/* Action Error Alerts */}
      {actionError && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-md text-xs font-medium text-left">
          {actionError}
        </div>
      )}

      {/* Main Table */}
      <div className="border border-zinc-200 rounded-md overflow-hidden bg-white">
        {maps.length === 0 ? (
          <div className="p-8 text-center bg-zinc-50/50">
            <p className="text-sm text-zinc-500 font-medium">No requirements assigned to this department.</p>
          </div>
        ) : (
          <Table>
            <TableHeader className="bg-zinc-50">
              <TableRow>
                <TableHead className="font-semibold text-xs text-zinc-700">What</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700">Deadline</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700">Status</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700">Confidence</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700">Evidence</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700">Judgment</TableHead>
                <TableHead className="font-semibold text-xs text-zinc-700 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {maps.map((mapItem) => {
                return (
                  <React.Fragment key={mapItem.id}>
                    <TableRow className="hover:bg-zinc-50/50">
                      <TableCell className="max-w-[450px] min-w-[250px] whitespace-normal break-words pr-4 text-xs font-medium text-zinc-900 text-left">
                        {mapItem.what}
                      </TableCell>
                      <TableCell className="text-xs text-zinc-500">
                        {new Date(mapItem.deadline).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={mapItem.status} />
                      </TableCell>
                      <TableCell>
                        <ConfidencePill score={mapItem.confidence_score} />
                      </TableCell>
                      <TableCell className="text-xs text-zinc-500 text-left">
                        {mapItem.latest_evidence ? (
                          <div className="flex flex-col gap-0.5" title={mapItem.latest_evidence.file_name}>
                            <span className="font-semibold text-zinc-800 truncate max-w-[100px]">
                              {mapItem.latest_evidence.file_name}
                            </span>
                            <span className="text-[10px] text-zinc-400">
                              By {mapItem.latest_evidence.submitted_by}
                            </span>
                          </div>
                        ) : (
                          <span className="text-zinc-300">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {mapItem.latest_judgment ? (
                          <div className="flex flex-col gap-0.5">
                            <StatusBadge status={mapItem.latest_judgment.verdict} />
                            {mapItem.latest_judgment.human_override && (
                              <span className="text-[9px] text-amber-600 font-bold uppercase">Overridden</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-zinc-300">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1.5">
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={actionLoading}
                            onClick={() => {
                              setActiveOverrideForm(null);
                              setActiveEvidenceForm(activeEvidenceForm === mapItem.id ? null : mapItem.id);
                            }}
                            className="text-[11px] font-semibold px-2 py-1 h-7 border-zinc-200 hover:bg-zinc-100 rounded"
                          >
                            Evidence
                          </Button>
                          {mapItem.latest_evidence && (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={actionLoading}
                              onClick={() => handleJudgeTrigger(mapItem.id, mapItem.latest_evidence)}
                              className="text-[11px] font-semibold px-2 py-1 h-7 border-zinc-200 hover:bg-zinc-100 rounded"
                            >
                              Judge
                            </Button>
                          )}
                          {mapItem.latest_judgment && (
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={actionLoading}
                              onClick={() => {
                                setActiveEvidenceForm(null);
                                setActiveOverrideForm(activeOverrideForm === mapItem.id ? null : mapItem.id);
                              }}
                              className="text-[11px] font-semibold px-2 py-1 h-7 border-zinc-200 hover:bg-zinc-100 rounded"
                            >
                              Override
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {/* Evidence Submission Form Row */}
                    {activeEvidenceForm === mapItem.id && (
                      <TableRow className="bg-zinc-50/50">
                        <TableCell colSpan={7} className="p-4 border-t border-zinc-200 whitespace-normal">
                          <form
                            onSubmit={(e) => handleEvidenceSubmit(e, mapItem.id)}
                            className="flex flex-col sm:flex-row items-end gap-4 max-w-2xl text-left"
                          >
                            <div className="flex-1 space-y-1.5">
                              <label className="text-xs font-bold text-zinc-700">Select Evidence File</label>
                              <Input
                                type="file"
                                disabled={actionLoading}
                                onChange={(e) => setEvidenceFile(e.target.files[0])}
                                className="text-xs rounded border-zinc-200 h-9 bg-white cursor-pointer"
                                required
                              />
                            </div>
                            <div className="flex-1 space-y-1.5">
                              <label className="text-xs font-bold text-zinc-700">Submitted By (Email)</label>
                              <Input
                                type="email"
                                placeholder="officer@bank.com"
                                value={submittedBy}
                                disabled={actionLoading}
                                onChange={(e) => setSubmittedBy(e.target.value)}
                                className="text-xs rounded border-zinc-200 h-9 bg-white"
                                required
                              />
                            </div>
                            <div className="flex gap-2">
                              <Button
                                type="submit"
                                disabled={actionLoading || !evidenceFile || !submittedBy}
                                className="bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-1.5 h-9 px-4 rounded"
                              >
                                Upload & Judge
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                disabled={actionLoading}
                                onClick={() => {
                                  setActiveEvidenceForm(null);
                                  setEvidenceFile(null);
                                  setSubmittedBy('');
                                }}
                                className="text-xs font-semibold border-zinc-200 hover:bg-zinc-100 py-1.5 h-9 px-3 rounded bg-white"
                              >
                                Cancel
                              </Button>
                            </div>
                          </form>
                        </TableCell>
                      </TableRow>
                    )}

                    {/* Override Judgment Form Row */}
                    {activeOverrideForm === mapItem.id && mapItem.latest_judgment && (
                      <TableRow className="bg-zinc-50/50">
                        <TableCell colSpan={7} className="p-4 border-t border-zinc-200 whitespace-normal">
                          <form
                            onSubmit={(e) => handleOverrideSubmit(e, mapItem.latest_judgment)}
                            className="space-y-4 max-w-2xl text-left"
                          >
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div className="space-y-1.5">
                                <label className="text-xs font-bold text-zinc-700">New Compliance Verdict</label>
                                <select
                                  value={overrideVerdict}
                                  disabled={actionLoading}
                                  onChange={(e) => setOverrideVerdict(e.target.value)}
                                  className="w-full text-xs rounded border border-zinc-200 h-9 px-3 bg-white focus:outline-none focus:ring-1 focus:ring-zinc-950"
                                >
                                  <option value="satisfied">Satisfied</option>
                                  <option value="partial">Partial</option>
                                  <option value="insufficient">Insufficient</option>
                                </select>
                              </div>
                              <div className="space-y-1.5">
                                <label className="text-xs font-bold text-zinc-700">Override Operator (Email)</label>
                                <Input
                                  type="email"
                                  placeholder="auditor@bank.com"
                                  value={overrideBy}
                                  disabled={actionLoading}
                                  onChange={(e) => setOverrideBy(e.target.value)}
                                  className="text-xs rounded border-zinc-200 h-9 bg-white"
                                  required
                                />
                              </div>
                            </div>
                            <div className="space-y-1.5">
                              <label className="text-xs font-bold text-zinc-700">Reason for Override</label>
                              <Input
                                type="text"
                                placeholder="Enter justification for modifying LLM verdict..."
                                value={overrideReason}
                                disabled={actionLoading}
                                onChange={(e) => setOverrideReason(e.target.value)}
                                className="text-xs rounded border-zinc-200 h-9 bg-white"
                                required
                              />
                            </div>
                            <div className="flex gap-2 justify-end">
                              <Button
                                type="submit"
                                disabled={actionLoading || !overrideBy || !overrideReason}
                                className="bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-1.5 h-9 px-4 rounded"
                              >
                                Apply Override
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                disabled={actionLoading}
                                onClick={() => {
                                  setActiveOverrideForm(null);
                                  setOverrideBy('');
                                  setOverrideReason('');
                                }}
                                className="text-xs font-semibold border-zinc-200 hover:bg-zinc-100 py-1.5 h-9 px-3 rounded bg-white"
                              >
                                Cancel
                              </Button>
                            </div>
                          </form>
                        </TableCell>
                      </TableRow>
                    )}

                    {/* Judgment Reasoning Row */}
                    {mapItem.latest_judgment && activeOverrideForm !== mapItem.id && (
                      <TableRow className="bg-zinc-50/10 border-b border-zinc-100">
                        <TableCell colSpan={7} className="py-2.5 px-4 text-left whitespace-normal">
                          <div className="bg-zinc-50 border border-zinc-200/80 rounded p-3 text-xs leading-relaxed text-zinc-700">
                            <span className="font-semibold text-zinc-900 block mb-1">
                              Independent Auditor Verdict:
                            </span>
                            {mapItem.latest_judgment.reasoning}
                            {mapItem.latest_judgment.human_override && (
                              <div className="mt-2 pt-2 border-t border-zinc-200 text-amber-800 font-medium">
                                ⚠️ Human Overridden by {mapItem.latest_judgment.override_by || 'Unknown'}: "{mapItem.latest_judgment.override_reason}"
                              </div>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </div>
  );
}
