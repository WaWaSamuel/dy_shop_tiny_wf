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

// ─── Fulfillment types ──────────────────────────────────────────────────────

export type FulfillmentListingStatus =
  | 'matching'
  | 'matched'
  | 'no_source'
  | 'listing'
  | 'listed'
  | 'listing_failed';

export interface FulfillmentListing {
  id: string;
  title: string;
  category: string;
  status: FulfillmentListingStatus;
  alibaba_offer_id: string | null;
  supplier_name: string;
  supplier_url: string;
  match_score: number;
  wholesale_price: number;
  landed_cost: number;
  sell_price: number;
  target_margin: number;
  achieved_margin: number;
  douyin_product_id: string | null;
  error_message: string | null;
  created_at: string;
}

export type FulfillmentOrderStatus =
  | 'received'
  | 'sourcing'
  | 'sourced'
  | 'shipped'
  | 'delivered'
  | 'fulfill_failed'
  | 'cancelled';

export interface FulfillmentSupplierOrder {
  id: string;
  alibaba_order_id: string | null;
  alibaba_offer_id: string | null;
  quantity: number;
  total_amount: number;
  status: string;
  tracking_no: string | null;
  logistics_company: string | null;
}

export interface FulfillmentOrder {
  id: string;
  listing_id: string | null;
  douyin_order_id: string;
  douyin_product_id: string | null;
  sku_id: string | null;
  quantity: number;
  buyer_paid_amount: number;
  status: FulfillmentOrderStatus;
  error_message: string | null;
  fulfilled_at: string | null;
  created_at: string;
  supplier_order: FulfillmentSupplierOrder | null;
}

export interface FulfillmentStats {
  listings_by_status: Record<string, number>;
  orders_by_status: Record<string, number>;
}

export interface SourceAndListResult {
  mode: string;
  task_id?: string | null;
  listing_id?: string | null;
  status?: string | null;
  match_score?: number | null;
  sell_price?: number | null;
  achieved_margin?: number | null;
  douyin_product_id?: string | null;
  error_message?: string | null;
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

// ─── Fulfillment API ──────────────────────────────────────────────────────────

export const fulfillmentApi = {
  listListings: (params?: { status?: string; limit?: number }) =>
    api.get<FulfillmentListing[]>('/fulfillment/listings', { params }),

  getListing: (id: string) =>
    api.get<FulfillmentListing>(`/fulfillment/listings/${id}`),

  sourceAndList: (data: {
    title: string;
    category?: string;
    image_url?: string | null;
    description?: string;
    asset_urls?: string[];
    source_candidate_id?: string | null;
    auto_publish?: boolean;
    async_mode?: boolean;
  }) => api.post<SourceAndListResult>('/fulfillment/source-and-list', data),

  listOrders: (params?: { status?: string; limit?: number }) =>
    api.get<FulfillmentOrder[]>('/fulfillment/orders', { params }),

  getOrder: (id: string) => api.get<FulfillmentOrder>(`/fulfillment/orders/${id}`),

  fulfillOrder: (id: string) =>
    api.post<FulfillmentOrder>(`/fulfillment/orders/${id}/fulfill`),

  getStats: () => api.get<FulfillmentStats>('/fulfillment/stats'),
};

export default api;
