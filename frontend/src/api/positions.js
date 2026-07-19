import { apiGet } from './api.js';

export async function getPositions() {
  return apiGet('/api/positions');
}
