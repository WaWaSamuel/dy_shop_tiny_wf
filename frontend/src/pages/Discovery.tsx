import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp,
  CheckCircle,
  XCircle,
  Scan,
  ArrowUpDown,
  Sparkles,
  MapPin,
  Star,
} from 'lucide-react';
import { discoveryApi, type ShortlistCandidate, type TrendingProduct } from '../services/api';
import { useLanguage } from '../i18n';

const mockShortlist: ShortlistCandidate[] = [
  {
    id: '1',
    product_name: 'Viral Ice Silk Cooling Scarf',
    trend_score: 95,
    margin_estimate: 62,
    supplier_info: { name: 'Yiwu Textile Co.', rating: 4.8, location: 'Zhejiang' },
    image_url: '/placeholder-product-1.jpg',
    recommendation_reason: 'Rising fast on Douyin - 200% increase in search volume this week',
    status: 'pending',
  },
  {
    id: '2',
    product_name: 'Portable Mini Fan - Neck Worn',
    trend_score: 88,
    margin_estimate: 55,
    supplier_info: { name: 'Shenzhen Cool Tech', rating: 4.6, location: 'Guangdong' },
    image_url: '/placeholder-product-2.jpg',
    recommendation_reason: 'Summer must-have, top sellers averaging 5000+ units/day',
    status: 'pending',
  },
  {
    id: '3',
    product_name: 'UV-Protection Bucket Hat',
    trend_score: 82,
    margin_estimate: 48,
    supplier_info: { name: 'Hangzhou Fashion', rating: 4.5, location: 'Zhejiang' },
    image_url: '/placeholder-product-3.jpg',
    recommendation_reason: 'Consistent summer demand, low return rate, good reviews',
    status: 'pending',
  },
  {
    id: '4',
    product_name: 'Self-Heating Eye Mask - Lavender',
    trend_score: 79,
    margin_estimate: 70,
    supplier_info: { name: 'Suzhou Wellness', rating: 4.9, location: 'Jiangsu' },
    image_url: '/placeholder-product-4.jpg',
    recommendation_reason: 'Wellness category trending, high margin and repeat purchase rate',
    status: 'pending',
  },
];

const mockTrending: TrendingProduct[] = [
  {
    id: '1',
    name: 'Dopamine Color Block T-Shirt',
    trend_score: 97,
    margin_estimate: 45,
    supplier: 'Guangzhou Fabric House',
    supplier_rating: 4.7,
    category: 'Women Clothing',
    daily_sales: 12000,
    source_url: '#',
  },
  {
    id: '2',
    name: 'Magnetic Phone Case - MagSafe',
    trend_score: 93,
    margin_estimate: 58,
    supplier: 'Shenzhen Tech Parts',
    supplier_rating: 4.5,
    category: 'Electronics',
    daily_sales: 8500,
    source_url: '#',
  },
  {
    id: '3',
    name: 'Korean Glass Skin Sunscreen',
    trend_score: 91,
    margin_estimate: 52,
    supplier: 'Guangzhou Beauty Lab',
    supplier_rating: 4.8,
    category: 'Beauty',
    daily_sales: 15000,
    source_url: '#',
  },
  {
    id: '4',
    name: 'Invisible Socks - 10 Pack',
    trend_score: 86,
    margin_estimate: 65,
    supplier: 'Yiwu Hosiery Mall',
    supplier_rating: 4.3,
    category: 'Accessories',
    daily_sales: 20000,
    source_url: '#',
  },
  {
    id: '5',
    name: 'Foldable Travel Water Bottle',
    trend_score: 84,
    margin_estimate: 60,
    supplier: 'Dongguan Plastec',
    supplier_rating: 4.6,
    category: 'Home',
    daily_sales: 6000,
    source_url: '#',
  },
];

export default function Discovery() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [sortBy, setSortBy] = useState<'trend_score' | 'margin_estimate' | 'daily_sales'>(
    'trend_score'
  );

  const { data: shortlistData } = useQuery({
    queryKey: ['shortlist'],
    queryFn: () => discoveryApi.getShortlist().then((r) => r.data),
  });

  const { data: trendingData } = useQuery({
    queryKey: ['trending', sortBy],
    queryFn: () => discoveryApi.getTrending({ sort_by: sortBy }).then((r) => r.data),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => discoveryApi.approveCandidate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shortlist'] }),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => discoveryApi.rejectCandidate(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['shortlist'] }),
  });

  const scanMutation = useMutation({
    mutationFn: () => discoveryApi.triggerScan(),
  });

  const shortlist = shortlistData?.items ?? mockShortlist;
  const trending = trendingData?.items ?? mockTrending;

  const sortedTrending = [...trending].sort((a, b) => b[sortBy] - a[sortBy]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('discovery.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {t('discovery.subtitle')}
          </p>
        </div>
        <button
          className="btn-primary flex items-center gap-2 text-sm"
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
        >
          <Scan className="w-4 h-4" />
          {scanMutation.isPending ? t('discovery.scanning') : t('discovery.triggerScan')}
        </button>
      </div>

      {/* Today's Shortlist */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-500" />
          {t('discovery.shortlist')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {shortlist.map((candidate) => (
            <ShortlistCard
              key={candidate.id}
              candidate={candidate}
              onApprove={() => approveMutation.mutate(candidate.id)}
              onReject={() => rejectMutation.mutate(candidate.id)}
            />
          ))}
        </div>
      </div>

      {/* Trending Products Table */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-brand-primary" />
            {t('discovery.trending')}
          </h2>
          <div className="flex items-center gap-2">
            <ArrowUpDown className="w-4 h-4 text-gray-400" />
            <select
              className="input-field w-auto text-sm"
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as 'trend_score' | 'margin_estimate' | 'daily_sales')
              }
            >
              <option value="trend_score">{t('discovery.trendScore')}</option>
              <option value="margin_estimate">{t('discovery.margin')}</option>
              <option value="daily_sales">{t('discovery.dailySales')}</option>
            </select>
          </div>
        </div>
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
                  {t('discovery.trendScore')}
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                  {t('discovery.margin')}
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                  {t('discovery.dailySales')}
                </th>
                <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                  {t('discovery.supplier')}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {sortedTrending.map((product) => (
                <tr key={product.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-5 py-3">
                    <span className="text-sm font-medium text-gray-900">{product.name}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm text-gray-600">{product.category}</span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-primary rounded-full"
                          style={{ width: `${product.trend_score}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-900">
                        {product.trend_score}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm font-medium text-green-600">
                      {product.margin_estimate}%
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <span className="text-sm text-gray-900">
                      {product.daily_sales.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-1">
                      <span className="text-sm text-gray-600">{product.supplier}</span>
                      <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
                      <span className="text-xs text-gray-400">{product.supplier_rating}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ShortlistCard({
  candidate,
  onApprove,
  onReject,
}: {
  candidate: ShortlistCandidate;
  onApprove: () => void;
  onReject: () => void;
}) {
  const { t } = useLanguage();
  return (
    <div className="card p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start gap-4">
        <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
          <TrendingUp className="w-6 h-6 text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-gray-900 truncate">
            {candidate.product_name}
          </h3>
          <p className="text-xs text-gray-500 mt-1">{candidate.recommendation_reason}</p>
          <div className="flex items-center gap-4 mt-3">
            <div className="flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5 text-brand-primary" />
              <span className="text-xs font-medium text-gray-700">
                {t('discovery.score')}: {candidate.trend_score}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="text-xs font-medium text-green-600">
                {t('discovery.margin')}: {candidate.margin_estimate}%
              </span>
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-xs text-gray-500">
                {candidate.supplier_info.location}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-gray-500">
              {candidate.supplier_info.name}
            </span>
            <Star className="w-3 h-3 text-amber-400 fill-amber-400" />
            <span className="text-xs text-gray-400">
              {candidate.supplier_info.rating}
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 mt-4 pt-4 border-t">
        <button
          className="btn-primary flex-1 flex items-center justify-center gap-1.5 text-sm py-2"
          onClick={onApprove}
        >
          <CheckCircle className="w-4 h-4" />
          {t('discovery.approve')}
        </button>
        <button
          className="btn-outline flex-1 flex items-center justify-center gap-1.5 text-sm py-2"
          onClick={onReject}
        >
          <XCircle className="w-4 h-4" />
          {t('discovery.reject')}
        </button>
      </div>
    </div>
  );
}
