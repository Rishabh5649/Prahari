import axios from 'axios';

export const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'X-API-Key': import.meta.env.VITE_API_KEY || '',
  },
});

// ── Global error state ──
// Components can subscribe to this by importing and checking lastApiError.
let _errorListeners = [];

export function onApiError(listener) {
  _errorListeners.push(listener);
  return () => {
    _errorListeners = _errorListeners.filter((l) => l !== listener);
  };
}

function _notifyError(message) {
  _errorListeners.forEach((l) => l(message));
}

// ── Response interceptor ──
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      const detail =
        error.response.data?.detail || error.response.data?.message || error.response.statusText;

      if (status >= 400 && status < 600) {
        const msg = `API Error ${status}: ${detail}`;
        console.error(msg);
        _notifyError(msg);
      }
    } else if (error.request) {
      const msg = 'Network error: could not reach the backend server.';
      console.error(msg);
      _notifyError(msg);
    }
    return Promise.reject(error);
  }
);

export default client;
