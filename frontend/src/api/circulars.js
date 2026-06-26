import client from './client';

export async function ingestUrl(url) {
  const response = await client.post('/api/ingest/url', { url });
  return response.data;
}

export async function ingestFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await client.post('/api/ingest/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
}
