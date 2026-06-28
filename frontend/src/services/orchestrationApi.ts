import api from './api';
import type { OrchestrationGraphPayload } from '@/types';

export async function getOrchestrationGraph(): Promise<OrchestrationGraphPayload> {
  return api.get('/v1/orchestration/graph');
}

