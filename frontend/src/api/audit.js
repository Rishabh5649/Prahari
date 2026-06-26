import client from './client';

export async function getAuditLogs(params = {}) {
  const response = await client.get('/api/audit', { params });
  return response.data;
}
