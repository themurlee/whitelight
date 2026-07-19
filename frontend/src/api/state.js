import { apiGet } from './api.js';

export async function getState() {
  return apiGet('/api/state');
}
