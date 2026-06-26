import api from './api';
import type { SessionSource } from '@/types';

interface SessionSourceApiResponse {
  id: string;
  name: string;
  description: string;
  homepage_url: string;
  login_url: string;
  domain_patterns: string[];
  project_keys: string[];
  auth_kind: string;
  probe_kind: string;
  probe_path: string;
  cookie_key: string;
  enabled: boolean;
  status: SessionSource['status'];
  severity: SessionSource['severity'];
  healthy: boolean;
  message: string;
  last_checked_at?: string | null;
  last_success_at?: string | null;
  last_error?: string | null;
  supports_browser_sync: boolean;
  has_stored_cookie: boolean;
  is_stale: boolean;
  probe_detail: {
    display_name?: string | null;
    user_vid?: string | null;
  };
}

const mapSessionSource = (item: SessionSourceApiResponse): SessionSource => ({
  id: item.id,
  name: item.name,
  description: item.description,
  homepageUrl: item.homepage_url,
  loginUrl: item.login_url,
  domainPatterns: item.domain_patterns,
  projectKeys: item.project_keys,
  authKind: item.auth_kind,
  probeKind: item.probe_kind,
  probePath: item.probe_path,
  cookieKey: item.cookie_key,
  enabled: item.enabled,
  status: item.status,
  severity: item.severity,
  healthy: item.healthy,
  message: item.message,
  lastCheckedAt: item.last_checked_at,
  lastSuccessAt: item.last_success_at,
  lastError: item.last_error,
  supportsBrowserSync: item.supports_browser_sync,
  hasStoredCookie: item.has_stored_cookie,
  isStale: item.is_stale,
  probeDetail: {
    displayName: item.probe_detail?.display_name,
    userVid: item.probe_detail?.user_vid,
  },
});

export const getSessionSources = async (refresh = false): Promise<SessionSource[]> => {
  const response = await api.get('/v1/session-sources', {
    params: refresh ? { refresh: true } : undefined,
  }) as SessionSourceApiResponse[];
  return response.map(mapSessionSource);
};

export const probeSessionSource = async (
  sourceId: string,
  refreshCookieFromBrowser = false,
): Promise<SessionSource> => {
  const response = await api.post(`/v1/session-sources/${sourceId}/probe`, {
    refresh_cookie_from_browser: refreshCookieFromBrowser,
  }) as SessionSourceApiResponse;
  return mapSessionSource(response);
};

export const reconnectSessionSource = async (sourceId: string): Promise<SessionSource> => {
  const response = await api.post(`/v1/session-sources/${sourceId}/reconnect`) as SessionSourceApiResponse;
  return mapSessionSource(response);
};

export const syncSessionSourceViaBridge = async (sourceId: string): Promise<SessionSource> => {
  const response = await api.post(`/v1/session-bridge/sync/${sourceId}`) as SessionSourceApiResponse;
  return mapSessionSource(response);
};
