import api from './api';
import type { RuntimeCapabilityCatalogItem, RuntimeExecutionRecord, RuntimeOverview } from '@/types';

export const getRuntimeOverview = () => {
  return api.get('/runtime/overview') as unknown as Promise<RuntimeOverview>;
};

export const getRuntimeCatalog = () => {
  return api.get('/runtime/catalog') as unknown as Promise<RuntimeCapabilityCatalogItem[]>;
};

export const getRuntimeLogs = (params?: {
  capability_kind?: string;
  capability_key?: string;
  workflow_id?: string;
  project_key?: string;
  status?: string;
  search?: string;
  limit?: number;
}) => {
  return api.get('/runtime/logs', { params }) as unknown as Promise<RuntimeExecutionRecord[]>;
};
