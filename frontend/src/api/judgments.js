import client from './client';

export async function judgeEvidence(mapId, evidenceId) {
  const response = await client.post(`/api/judgments/${mapId}/judge`, {
    evidence_id: evidenceId,
  });
  return response.data;
}

export async function overrideJudgment(judgmentId, { newVerdict, overrideBy, overrideReason }) {
  const response = await client.post(`/api/judgments/${judgmentId}/override`, {
    new_verdict: newVerdict,
    override_by: overrideBy,
    override_reason: overrideReason,
  });
  return response.data;
}

export async function getJudgments(mapId) {
  const response = await client.get(`/api/judgments/${mapId}`);
  return response.data;
}
