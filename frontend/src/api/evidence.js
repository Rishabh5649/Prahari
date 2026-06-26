import client from './client';

export async function submitEvidence(mapId, file, submittedBy) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('submitted_by', submittedBy);
  const response = await client.post(`/api/evidence/${mapId}/submit`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}
