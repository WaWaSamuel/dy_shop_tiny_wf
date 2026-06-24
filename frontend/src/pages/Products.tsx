import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Plus,
  Upload,
  Search,
  Package,
  Eye,
  Rocket,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { productsApi, type Product } from '../services/api';
import { useLanguage } from '../i18n';

const mockProducts: Product[] = [
  {
    id: '1',
    name: 'Summer Floral Dress - V-Neck',
    category: 'Women Clothing',
    status: 'online',
    price: 128.0,
    sku_count: 6,
    images: ['/placeholder-1.jpg'],
    created_at: '2024-06-10T08:00:00Z',
    updated_at: '2024-06-12T10:00:00Z',
  },
  {
    id: '2',
    name: 'Casual Denim Jacket - Oversized',
    category: 'Women Clothing',
    status: 'under_review',
    price: 259.0,
    sku_count: 4,
    images: ['/placeholder-2.jpg'],
    created_at: '2024-06-14T09:00:00Z',
    updated_at: '2024-06-14T09:30:00Z',
  },
  {
    id: '3',
    name: 'Minimalist Leather Crossbody Bag',
    category: 'Accessories',
    status: 'approved',
    price: 189.0,
    sku_count: 3,
    images: ['/placeholder-3.jpg'],
    created_at: '2024-06-13T14:00:00Z',
    updated_at: '2024-06-15T08:00:00Z',
  },
  {
    id: '4',
    name: 'Sports Running Shoes - Breathable',
    category: 'Shoes',
    status: 'draft',
    price: 329.0,
    sku_count: 8,
    images: ['/placeholder-4.jpg'],
    created_at: '2024-06-15T11:00:00Z',
    updated_at: '2024-06-15T11:00:00Z',
  },
  {
    id: '5',
    name: 'Silk Pajama Set - Luxe',
    category: 'Women Clothing',
    status: 'uploading',
    price: 199.0,
    sku_count: 4,
    images: ['/placeholder-5.jpg'],
    created_at: '2024-06-15T12:00:00Z',
    updated_at: '2024-06-15T12:05:00Z',
  },
  {
    id: '6',
    name: 'Retro Sunglasses - Cat Eye',
    category: 'Accessories',
    status: 'online',
    price: 79.0,
    sku_count: 5,
    images: ['/placeholder-6.jpg'],
    created_at: '2024-06-08T10:00:00Z',
    updated_at: '2024-06-10T15:00:00Z',
  },
];

export default function Products() {
  const { t } = useLanguage();
  const [showNewForm, setShowNewForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: productData } = useQuery({
    queryKey: ['products', statusFilter],
    queryFn: () =>
      productsApi.list({ status: statusFilter || undefined }).then((r) => r.data),
  });

  const products = productData?.items ?? mockProducts;

  const filteredProducts = products.filter((p) => {
    if (statusFilter && p.status !== statusFilter) return false;
    if (searchQuery && !p.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('products.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('products.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="btn-outline flex items-center gap-2 text-sm">
            <Upload className="w-4 h-4" />
            {t('products.batchUpload')}
          </button>
          <button
            className="btn-primary flex items-center gap-2 text-sm"
            onClick={() => setShowNewForm(true)}
          >
            <Plus className="w-4 h-4" />
            {t('products.newProduct')}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder={t('products.searchPlaceholder')}
              className="input-field pl-9"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <select
            className="input-field w-auto"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">{t('filters.allStatus')}</option>
            <option value="draft">{t('status.draft')}</option>
            <option value="uploading">{t('status.uploading')}</option>
            <option value="under_review">{t('status.under_review')}</option>
            <option value="approved">{t('status.approved')}</option>
            <option value="online">{t('status.online')}</option>
            <option value="rejected">{t('status.rejected')}</option>
          </select>
        </div>
      </div>

      {/* Product List */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-gray-50/50">
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.product')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.category')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.price')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.skus')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.status')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('products.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filteredProducts.map((product) => (
              <tr key={product.id} className="hover:bg-gray-50/50 transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                      <Package className="w-5 h-5 text-gray-400" />
                    </div>
                    <span className="text-sm font-medium text-gray-900">{product.name}</span>
                  </div>
                </td>
                <td className="px-5 py-3">
                  <span className="text-sm text-gray-600">{product.category}</span>
                </td>
                <td className="px-5 py-3">
                  <span className="text-sm font-medium text-gray-900">
                    ¥{product.price.toFixed(2)}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className="text-sm text-gray-600">{product.sku_count}</span>
                </td>
                <td className="px-5 py-3">
                  <StatusBadge status={product.status} />
                </td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2">
                    <button className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors">
                      <Eye className="w-4 h-4 text-gray-500" />
                    </button>
                    {product.status === 'approved' && (
                      <button className="p-1.5 rounded-lg hover:bg-green-50 transition-colors">
                        <Rocket className="w-4 h-4 text-green-600" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* New Product Modal */}
      {showNewForm && (
        <NewProductModal onClose={() => setShowNewForm(false)} />
      )}
    </div>
  );
}

function NewProductModal({ onClose }: { onClose: () => void }) {
  const [formData, setFormData] = useState({
    name: '',
    category: '',
    price: '',
    skuName: '',
    skuPrice: '',
    skuStock: '',
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold text-gray-900">New Product</h2>
          <p className="text-sm text-gray-500 mt-1">Create a new product listing</p>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Product Name
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="Enter product name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <select
              className="input-field"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            >
              <option value="">Select category</option>
              <option value="women_clothing">Women Clothing</option>
              <option value="men_clothing">Men Clothing</option>
              <option value="accessories">Accessories</option>
              <option value="shoes">Shoes</option>
              <option value="bags">Bags</option>
              <option value="beauty">Beauty</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Price (CNY)
            </label>
            <input
              type="number"
              className="input-field"
              placeholder="0.00"
              value={formData.price}
              onChange={(e) => setFormData({ ...formData, price: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Images</label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-brand-primary/50 transition-colors cursor-pointer">
              <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                Click or drag images here to upload
              </p>
              <p className="text-xs text-gray-400 mt-1">PNG, JPG up to 5MB each</p>
            </div>
          </div>
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">SKU Information</h4>
            <div className="grid grid-cols-3 gap-3">
              <input
                type="text"
                className="input-field"
                placeholder="SKU Name"
                value={formData.skuName}
                onChange={(e) => setFormData({ ...formData, skuName: e.target.value })}
              />
              <input
                type="number"
                className="input-field"
                placeholder="Price"
                value={formData.skuPrice}
                onChange={(e) => setFormData({ ...formData, skuPrice: e.target.value })}
              />
              <input
                type="number"
                className="input-field"
                placeholder="Stock"
                value={formData.skuStock}
                onChange={(e) => setFormData({ ...formData, skuStock: e.target.value })}
              />
            </div>
            <button className="text-sm text-brand-primary font-medium mt-2 hover:underline">
              + Add another SKU
            </button>
          </div>
        </div>
        <div className="p-6 border-t flex items-center justify-end gap-3">
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn-primary" onClick={onClose}>
            Create Product
          </button>
        </div>
      </div>
    </div>
  );
}
