import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ingestUrl, ingestFile } from '@/api/circulars';

export default function IngestPage() {
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null); // { id, title, total_maps, pending_review }

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    if (!url) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await ingestUrl(url);
      setResult({
        id: data.circular_id,
        title: 'Ingested Circular',
        total_maps: data.maps_extracted || 0,
        pending_review: data.pending_review || 0,
      });
      setUrl('');
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errorMsg = typeof detail === 'string'
        ? detail
        : (Array.isArray(detail)
            ? detail.map((x) => x.msg).join(', ')
            : 'Failed to ingest URL. Please check if the source is accessible.');
      setError(errorMsg);
    } finally {
      setUrl('');
      setLoading(false);
    }
  };

  const handleFileSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await ingestFile(file);
      setResult({
        id: data.circular_id,
        title: file.name || 'Uploaded Circular',
        total_maps: data.maps_extracted || 0,
        pending_review: data.pending_review || 0,
      });
      setFile(null);
      // Reset input element
      document.getElementById('pdf-file-input').value = '';
    } catch (err) {
      const detail = err.response?.data?.detail;
      const errorMsg = typeof detail === 'string'
        ? detail
        : (Array.isArray(detail)
            ? detail.map((x) => x.msg).join(', ')
            : 'Failed to upload and process PDF file.');
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 py-6 px-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">Ingest Regulatory Circular</h1>
        <p className="text-sm text-zinc-500">
          Ingest new circulars from RBI, SEBI, or DPDP. The system will automatically parse the document, extract Mandatory Action Points (MAPs), and route them.
        </p>
      </div>

      {loading && (
        <Card className="border border-zinc-200 bg-zinc-50/50">
          <CardContent className="flex flex-col items-center justify-center p-8 gap-3">
            <div className="w-8 h-8 border-4 border-zinc-900 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-sm font-medium text-zinc-800">Processing circular...</p>
            <p className="text-xs text-zinc-500">Parsing document structure and running extractor agent...</p>
          </CardContent>
        </Card>
      )}

      {result && (
        <Card className="border border-emerald-200 bg-emerald-50/20">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-emerald-800 text-sm font-semibold">Ingestion Successful</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0 space-y-3">
            <p className="text-sm text-zinc-700">
              Extracted <strong className="font-semibold text-zinc-900">{result.total_maps}</strong> MAPs.
              {result.pending_review > 0 ? (
                <> <strong className="font-semibold text-orange-700">{result.pending_review}</strong> flagged for review.</>
              ) : (
                ' None flagged for review.'
              )}
            </p>
            <div className="pt-1">
              <Link to={`/circular/${result.id}`}>
                <Button className="bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold px-4 py-1.5 h-auto rounded">
                  View MAPs & Actions →
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border border-red-200 bg-red-50/20">
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-red-800 text-sm font-semibold">Ingestion Failed</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <p className="text-xs font-medium text-red-700 leading-relaxed">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* URL Ingestion */}
        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4">
            <CardTitle className="text-sm font-bold text-zinc-900">Ingest via URL</CardTitle>
            <CardDescription className="text-xs text-zinc-500">
              Enter a direct PDF link or a web page URL.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <Input
                type="url"
                placeholder="https://rbi.org.in/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={loading}
                className="text-xs rounded border-zinc-200 h-9"
                required
              />
              <Button
                type="submit"
                disabled={loading || !url}
                className="w-full bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-1.5 h-9 rounded"
              >
                Ingest URL
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* PDF Ingestion */}
        <Card className="border border-zinc-200 shadow-sm bg-white">
          <CardHeader className="p-4">
            <CardTitle className="text-sm font-bold text-zinc-900">Upload PDF File</CardTitle>
            <CardDescription className="text-xs text-zinc-500">
              Select a PDF document from your local storage.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <form onSubmit={handleFileSubmit} className="space-y-4">
              <Input
                id="pdf-file-input"
                type="file"
                accept=".pdf"
                onChange={(e) => setFile(e.target.files[0])}
                disabled={loading}
                className="text-xs rounded border-zinc-200 h-9 cursor-pointer file:text-xs file:font-semibold file:bg-zinc-100 file:text-zinc-800 file:border-0 file:rounded file:px-2 file:py-1 file:mr-2"
                required
              />
              <Button
                type="submit"
                disabled={loading || !file}
                className="w-full bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-semibold py-1.5 h-9 rounded"
              >
                Upload & Process
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
