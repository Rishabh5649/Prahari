import client from './client';

export async function getStats() {
  const response = await client.get('/api/dashboard/stats');
  return response.data;
}

export async function getCirculars() {
  const response = await client.get('/api/dashboard/circulars');
  return response.data;
}

export async function getCircularDetail(circularId) {
  const response = await client.get(`/api/dashboard/circulars/${circularId}`);
  return response.data;
}

export async function getDepartmentMaps(deptName) {
  const response = await client.get(`/api/dashboard/department/${deptName}`);
  return response.data;
}
