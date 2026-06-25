import api from './api';
import type { Product, Order, FlowNodeData, CreativeAsset } from '@/types';

// Products
export const getProducts = (params?: {
  page?: number;
  pageSize?: number;
  status?: string;
  keyword?: string;
  platform?: string;
}) => {
  return api.get<{ items: Product[]; total: number }>('/ecommerce/products', { params });
};

export const getProductById = (id: string) => {
  return api.get<Product>(`/ecommerce/products/${id}`);
};

export const createProduct = (data: Partial<Product>) => {
  return api.post<Product>('/ecommerce/products', data);
};

export const updateProduct = (id: string, data: Partial<Product>) => {
  return api.put<Product>(`/ecommerce/products/${id}`, data);
};

export const deleteProduct = (id: string) => {
  return api.delete(`/ecommerce/products/${id}`);
};

// Orders
export const getOrders = (params?: {
  page?: number;
  pageSize?: number;
  status?: string;
  keyword?: string;
  platform?: string;
  startDate?: string;
  endDate?: string;
}) => {
  return api.get<{ items: Order[]; total: number }>('/ecommerce/orders', { params });
};

export const getOrderById = (id: string) => {
  return api.get<Order>(`/ecommerce/orders/${id}`);
};

export const updateOrderStatus = (id: string, status: string) => {
  return api.patch(`/ecommerce/orders/${id}/status`, { status });
};

// Sourcing
export const getSourcingProducts = (params?: {
  source?: string;
  keyword?: string;
  category?: string;
  page?: number;
  pageSize?: number;
}) => {
  return api.get('/ecommerce/sourcing/products', { params });
};

export const getSuppliers = (params?: { keyword?: string; source?: string }) => {
  return api.get('/ecommerce/sourcing/suppliers', { params });
};

// Creative Studio
export const generateCreativeAsset = (data: {
  category: string;
  pipeline: string;
  engine: string;
  prompt: string;
  systemWords: string[];
  productId?: string;
}) => {
  return api.post<CreativeAsset>('/ecommerce/creative/generate', data);
};

export const getCreativeAssets = (params?: {
  productId?: string;
  category?: string;
  page?: number;
  pageSize?: number;
}) => {
  return api.get<{ items: CreativeAsset[]; total: number }>('/ecommerce/creative/assets', { params });
};

export const getCreativeAssetById = (id: string) => {
  return api.get<CreativeAsset>(`/ecommerce/creative/assets/${id}`);
};

// Flow
export const getProductFlow = (productId: string) => {
  return api.get<FlowNodeData[]>(`/ecommerce/flow/${productId}`);
};

export const updateFlowNode = (productId: string, nodeId: string, data: Partial<FlowNodeData>) => {
  return api.patch<FlowNodeData>(`/ecommerce/flow/${productId}/nodes/${nodeId}`, data);
};

export const triggerFlowAction = (productId: string, nodeId: string, action: string) => {
  return api.post(`/ecommerce/flow/${productId}/nodes/${nodeId}/actions`, { action });
};
