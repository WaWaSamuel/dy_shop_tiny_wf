import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FeedbackItem {
  id: string;
  order_id: string;
  customer_name: string;
  content: string;
  type: 'complaint' | 'inquiry' | 'review' | 'return_request';
  source: 'douyin' | 'im' | 'phone';
  status: 'pending' | 'ai_drafted' | 'approved' | 'replied' | 'escalated';
  urgency: 'low' | 'medium' | 'high' | 'critical';
  sentiment_score: number;
  ai_draft_reply: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackStats {
  total_today: number;
  pending_responses: number;
  avg_response_time_min: number;
  auto_reply_rate: number;
  sentiment_breakdown: { positive: number; neutral: number; negative: number };
}

export interface Product {
  id: string;
  name: string;
  category: string;
  status: 'draft' | 'uploading' | 'under_review' | 'approved' | 'online' | 'rejected';
  price: number;
  sku_count: number;
  images: string[];
  created_at: string;
  updated_at: string;
}

export interface TrendingProduct {
  id: string;
  name: string;
  trend_score: number;
  margin_estimate: number;
  supplier: string;
  supplier_rating: number;
  category: string;
  daily_sales: number;
  source_url: string;
}

export interface ShortlistCandidate {
  id: string;
  product_name: string;
  trend_score: number;
  margin_estimate: number;
  supplier_info: { name: string; rating: number; location: string };
  image_url: string;
  recommendation_reason: string;
  status: 'pending' | 'approved' | 'rejected';
}

export interface DesignTask {
  id: string;
  product_id: string;
  product_name: string;
  task_type: 'main_image' | 'detail_page' | 'video_cover' | 'banner';
  style_template: string;
  status: 'queued' | 'generating' | 'completed' | 'approved' | 'rejected';
  thumbnail_url: string | null;
  output_urls: string[];
  created_at: string;
}

export interface DesignTemplate {
  id: string;
  name: string;
  preview_url: string;
  task_type: string;
}

// ─── Feedback API ─────────────────────────────────────────────────────────────

export const feedbackApi = {
  list: (params?: {
    status?: string;
    type?: string;
    source?: string;
    urgency?: string;
    page?: number;
    limit?: number;
  }) => api.get<{ items: FeedbackItem[]; total: number }>('/feedback', { params }),

  get: (id: string) => api.get<FeedbackItem>(`/feedback/${id}`),

  approve: (id: string) => api.post(`/feedback/${id}/approve`),

  reply: (id: string, data: { reply_content: string }) =>
    api.post(`/feedback/${id}/reply`, data),

  getStats: () => api.get<FeedbackStats>('/feedback/stats'),
};

// ─── Products API ─────────────────────────────────────────────────────────────

export const productsApi = {
  list: (params?: { status?: string; page?: number; limit?: number }) =>
    api.get<{ items: Product[]; total: number }>('/products', { params }),

  create: (data: {
    name: string;
    category: string;
    price: number;
    skus: Array<{ name: string; price: number; stock: number }>;
    images: string[];
  }) => api.post<Product>('/products', data),

  batchUpload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/products/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getStatus: (id: string) => api.get<{ status: string }>(`/products/${id}/status`),

  publish: (id: string) => api.post(`/products/${id}/publish`),
};

// ─── Discovery API ────────────────────────────────────────────────────────────

export const discoveryApi = {
  getTrending: (params?: { category?: string; sort_by?: string; limit?: number }) =>
    api.get<{ items: TrendingProduct[]; total: number }>('/discovery/trending', { params }),

  getShortlist: () => api.get<{ items: ShortlistCandidate[] }>('/discovery/shortlist'),

  approveCandidate: (id: string) => api.post(`/discovery/shortlist/${id}/approve`),

  rejectCandidate: (id: string) => api.post(`/discovery/shortlist/${id}/reject`),

  triggerScan: () => api.post('/discovery/scan'),
};

// ─── Design API ───────────────────────────────────────────────────────────────

export const designApi = {
  list: (params?: { status?: string; page?: number; limit?: number }) =>
    api.get<{ items: DesignTask[]; total: number }>('/design/tasks', { params }),

  create: (data: { product_id: string; task_type: string; style_template: string }) =>
    api.post<DesignTask>('/design/tasks', data),

  get: (id: string) => api.get<DesignTask>(`/design/tasks/${id}`),

  regenerate: (id: string) => api.post(`/design/tasks/${id}/regenerate`),

  getTemplates: () => api.get<{ items: DesignTemplate[] }>('/design/templates'),
};

export default api;
