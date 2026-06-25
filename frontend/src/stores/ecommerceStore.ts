import { create } from 'zustand';
import type { Product, Order, FlowNodeData } from '@/types';

interface EcommerceState {
  products: Product[];
  currentProduct: Product | null;
  orders: Order[];
  flowNodes: FlowNodeData[];
  loading: boolean;
  setProducts: (products: Product[]) => void;
  setCurrentProduct: (product: Product | null) => void;
  setOrders: (orders: Order[]) => void;
  setFlowNodes: (nodes: FlowNodeData[]) => void;
  setLoading: (loading: boolean) => void;
  addProduct: (product: Product) => void;
  updateProduct: (id: string, data: Partial<Product>) => void;
  removeProduct: (id: string) => void;
}

export const useEcommerceStore = create<EcommerceState>((set) => ({
  products: [],
  currentProduct: null,
  orders: [],
  flowNodes: [],
  loading: false,
  setProducts: (products) => set({ products }),
  setCurrentProduct: (product) => set({ currentProduct: product }),
  setOrders: (orders) => set({ orders }),
  setFlowNodes: (nodes) => set({ flowNodes: nodes }),
  setLoading: (loading) => set({ loading }),
  addProduct: (product) =>
    set((state) => ({ products: [...state.products, product] })),
  updateProduct: (id, data) =>
    set((state) => ({
      products: state.products.map((p) => (p.id === id ? { ...p, ...data } : p)),
    })),
  removeProduct: (id) =>
    set((state) => ({
      products: state.products.filter((p) => p.id !== id),
    })),
}));
