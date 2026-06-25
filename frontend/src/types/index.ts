// Product
export interface Product {
  id: string;
  name: string;
  sku: string;
  image: string;
  price: number;
  cost: number;
  stock: number;
  status: 'active' | 'inactive' | 'out_of_stock' | 'low_stock';
  platform: string;
  category: string;
  createdAt: string;
  updatedAt?: string;
  description?: string;
  variants?: ProductVariant[];
  tags?: string[];
}

export interface ProductVariant {
  id: string;
  name: string;
  sku: string;
  price: number;
  stock: number;
  attributes: Record<string, string>;
}

// Order
export interface Order {
  id: string;
  orderId: string;
  productName: string;
  buyerName: string;
  amount: number;
  quantity: number;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled' | 'refunded';
  platform: string;
  trackingNo: string;
  createdAt: string;
  shippedAt: string;
  deliveredAt?: string;
  buyerAddress?: string;
  note?: string;
}

// Flow Node
export interface FlowNodeData extends Record<string, unknown> {
  id: string;
  label: string;
  status: 'completed' | 'running' | 'pending' | 'failed';
  timestamp: string;
  description?: string;
  logs?: FlowLog[];
  relatedLinks?: RelatedLink[];
  metadata?: Record<string, unknown>;
}

export interface FlowLog {
  id: string;
  time: string;
  content: string;
  type: 'info' | 'success' | 'warning' | 'error';
}

export interface RelatedLink {
  title: string;
  url: string;
  type?: string;
}

// Creative Asset
export interface CreativeAsset {
  id: string;
  productId?: string;
  category: 'main_image' | 'detail_page' | 'video_cover' | 'ad_banner' | 'social_post';
  pipeline: 'text2img' | 'img2img' | 'inpaint' | 'upscale' | 'video';
  engine: string;
  prompt: string;
  systemWords: string[];
  imageUrl: string;
  thumbnailUrl: string;
  status: 'generating' | 'completed' | 'failed';
  starred: boolean;
  version: number;
  createdAt: string;
  metadata?: Record<string, unknown>;
}

// Shop / Platform
export interface Shop {
  id: string;
  name: string;
  platform: 'tiktok_shop' | 'temu' | 'shopify' | 'amazon';
  status: 'active' | 'inactive' | 'suspended';
  url: string;
  apiKey?: string;
  createdAt: string;
  metrics?: ShopMetrics;
}

export interface ShopMetrics {
  totalProducts: number;
  totalOrders: number;
  totalRevenue: number;
  rating: number;
}

// Provider / Supplier
export interface Provider {
  id: string;
  name: string;
  source: 'alibaba_1688' | 'pinduoduo' | 'taobao' | 'direct_factory';
  contactName: string;
  contactPhone: string;
  location: string;
  rating: number;
  totalOrders: number;
  minOrderAmount: number;
  deliveryDays: number;
  categories: string[];
  verified: boolean;
  createdAt: string;
}

// Pagination
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

// API Response
export interface ApiResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}
