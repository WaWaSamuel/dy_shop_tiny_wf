import api from './api';
import type { NewsDigest, NewsDigestItem, NewsDigestPushRecord, NewsSource, NewsTopic } from '@/types';

interface NewsDigestApiResponse {
  window: {
    start: string;
    end: string;
    timezone: string;
    label: string;
  };
  refreshed_at: string;
  total_sources: number;
  total_articles: number;
  topics: Array<{
    topic: string;
    count: number;
    sources: string[];
  }>;
  sources: Array<{
    id: string;
    name: string;
    feed_url: string;
    homepage_url?: string | null;
    article_count: number;
    status: string;
    last_error?: string | null;
    fetched_at?: string | null;
  }>;
  items: Array<{
    id: string;
    title: string;
    source_id: string;
    source_name: string;
    url: string;
    published_at: string;
    summary: string;
    highlights: string[];
    excerpt: string;
  }>;
  notes: string[];
  mode: string;
  generated_by?: string | null;
  push_records: Array<{
    id: string;
    pushed_at: string;
    title: string;
    content: string;
    item_count: number;
    status: 'sent' | 'failed';
    target_hint: string;
    receive_id_type: string;
    receive_id: string;
    message_id?: string | null;
    error_detail?: string | null;
  }>;
}

const mapTopic = (topic: NewsDigestApiResponse['topics'][number]): NewsTopic => ({
  topic: topic.topic,
  count: topic.count,
  sources: topic.sources,
});

const mapSource = (source: NewsDigestApiResponse['sources'][number]): NewsSource => ({
  id: source.id,
  name: source.name,
  feedUrl: source.feed_url,
  homepageUrl: source.homepage_url,
  articleCount: source.article_count,
  status: source.status,
  lastError: source.last_error,
  fetchedAt: source.fetched_at,
});

const mapItem = (item: NewsDigestApiResponse['items'][number]): NewsDigestItem => ({
  id: item.id,
  title: item.title,
  sourceId: item.source_id,
  sourceName: item.source_name,
  url: item.url,
  publishedAt: item.published_at,
  summary: item.summary,
  highlights: item.highlights,
  excerpt: item.excerpt,
});

const mapPushRecord = (record: NewsDigestApiResponse['push_records'][number]): NewsDigestPushRecord => ({
  id: record.id,
  pushedAt: record.pushed_at,
  title: record.title,
  content: record.content,
  itemCount: record.item_count,
  status: record.status,
  targetHint: record.target_hint,
  receiveIdType: record.receive_id_type,
  receiveId: record.receive_id,
  messageId: record.message_id,
  errorDetail: record.error_detail,
});

const mapDigest = (payload: NewsDigestApiResponse): NewsDigest => ({
  window: payload.window,
  refreshedAt: payload.refreshed_at,
  totalSources: payload.total_sources,
  totalArticles: payload.total_articles,
  topics: payload.topics.map(mapTopic),
  sources: payload.sources.map(mapSource),
  items: payload.items.map(mapItem),
  notes: payload.notes,
  mode: payload.mode,
  generatedBy: payload.generated_by,
  pushRecords: payload.push_records.map(mapPushRecord),
});

export const getNewsDigest = async (refresh = false): Promise<NewsDigest> => {
  const response = await api.get('/v1/news/digest', {
    params: refresh ? { refresh: true } : undefined,
  }) as NewsDigestApiResponse;
  return mapDigest(response);
};

export const refreshNewsDigest = async (): Promise<NewsDigest> => {
  const response = await api.post('/v1/news/digest/refresh') as NewsDigestApiResponse;
  return mapDigest(response);
};

export const getNewsSources = async (): Promise<NewsSource[]> => {
  const response = await api.get('/v1/news/sources') as NewsDigestApiResponse['sources'];
  return response.map(mapSource);
};

interface NewsDigestPushItemRequest {
  title: string;
  url?: string;
  summary?: string;
}

interface NewsDigestPushRequest {
  title: string;
  content?: string;
  items: NewsDigestPushItemRequest[];
  open_id?: string;
  chat_id?: string;
}

interface NewsDigestPushResponse {
  success: boolean;
  status: 'sent' | 'failed';
  receive_id_type: string;
  receive_id: string;
  target_hint: string;
  message_id?: string | null;
  record_id?: string | null;
  pushed_at?: string | null;
  error_detail?: string | null;
}

export const pushNewsDigest = async (payload: NewsDigestPushRequest): Promise<NewsDigestPushResponse> => {
  const response = await api.post('/v1/news/digest/push', payload) as NewsDigestPushResponse;
  return response;
};

interface BrowserNewsDigestSubmitRequest {
  window?: {
    start?: string;
    end?: string;
  };
  topics?: Array<{
    topic: string;
    count?: number;
    sources?: string[];
  }>;
  sources?: Array<{
    id?: string;
    name: string;
    homepage_url?: string;
    feed_url?: string;
    article_count?: number;
    status?: string;
    last_error?: string;
    fetched_at?: string;
  }>;
  items: Array<{
    id?: string;
    title: string;
    source_id?: string;
    source_name: string;
    url: string;
    published_at?: string;
    summary: string;
    highlights?: string[];
    excerpt?: string;
  }>;
  notes?: string[];
  mode?: string;
  generated_by?: string;
}

export const submitBrowserNewsDigest = async (payload: BrowserNewsDigestSubmitRequest): Promise<NewsDigest> => {
  const response = await api.post('/v1/news/digest/submit', payload) as NewsDigestApiResponse;
  return mapDigest(response);
};
