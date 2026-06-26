import client from './client';

export async function getMapsForCircular(circularId) {
  const response = await client.get(`/api/maps/circular/${circularId}`);
  return response.data;
}

export async function getMapDetail(mapId) {
  const response = await client.get(`/api/maps/${mapId}`);
  return response.data;
}

export async function getPendingReviewMaps() {
  const response = await client.get('/api/maps', { params: { status: 'pending_review' } });
  return response.data;
}

export async function approveMap(mapId, approvedBy = 'Compliance Officer') {
  const response = await client.patch(`/api/maps/${mapId}/approve`, {
    approved_by: approvedBy,
  });
  return response.data;
}

export async function rejectMap(mapId, rejectedBy, reason) {
  const response = await client.patch(`/api/maps/${mapId}/reject`, {
    rejected_by: rejectedBy,
    reason,
  });
  return response.data;
}
