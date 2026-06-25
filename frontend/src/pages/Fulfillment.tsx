import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Truck,
  Plus,
  Package,
  Store,
  ShoppingCart,
  CheckCircle2,
  ExternalLink,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import {
  fulfillmentApi,
  type FulfillmentListing,
  type FulfillmentOrder,
} from '../services/api';
import { useLanguage } from '../i18n';

const mockListings: FulfillmentListing[] = [
  {
    id: 'l1',
    title: '冰丝防晒凉感围巾',
    category: '服饰配件',
    status: 'listed',
    alibaba_offer_id: '654321098',
    supplier_name: '义乌纺织优选',
    supplier_url: 'https://detail.1688.com/offer/654321098.html',
    match_score: 0.86,
    wholesale_price: 8.5,
    landed_cost: 12.4,
    sell_price: 28.9,
    target_margin: 0.1,
    achieved_margin: 0.31,
    douyin_product_id: '37500001',
    error_message: null,
    created_at: '2024-06-20T08:00:00Z',
  },
  {
    id: 'l2',
    title: '便携挂脖小风扇',
    category: '数码配件',
    status: 'matched',
    alibaba_offer_id: '778899001',
    supplier_name: '深圳酷凉科技',
    supplier_url: 'https://detail.1688.com/offer/778899001.html',
    match_score: 0.79,
    wholesale_price: 14.0,
    landed_cost: 19.2,
    sell_price: 39.9,
    target_margin: 0.1,
    achieved_margin: 0.27,
    douyin_product_id: null,
    error_message: null,
    created_at: '2024-06-21T09:30:00Z',
  },
  {
    id: 'l3',
    title: '复古猫眼太阳镜',
    category: '配件',
    status: 'no_source',
    alibaba_offer_id: null,
    supplier_name: '',
    supplier_url: '',
    match_score: 0.41,
    wholesale_price: 0,
    landed_cost: 0,
    sell_price: 0,
    target_margin: 0.1,
    achieved_margin: 0,
    douyin_product_id: null,
    error_message: '未找到达标的同源货品',
    created_at: '2024-06-22T10:00:00Z',
  },
];

const mockOrders: FulfillmentOrder[] = [
  {
    id: 'o1',
    listing_id: 'l1',
    douyin_order_id: '6920000001',
    douyin_product_id: '37500001',
    sku_id: 'S1',
    quantity: 2,
    buyer_paid_amount: 57.8,
    status: 'shipped',
    error_message: null,
    fulfilled_at: '2024-06-23T12:00:00Z',
    created_at: '2024-06-23T11:30:00Z',
    supplier_order: {
      id: 'so1',
      alibaba_order_id: '2099887766',
      alibaba_offer_id: '654321098',
      quantity: 2,
      total_amount: 24.8,
      status: 'shipped',
      tracking_no: 'SF1234567890',
      logistics_company: '顺丰速运',
    },
  },
  {
    id: 'o2',
    listing_id: 'l1',
    douyin_order_id: '6920000002',
    douyin_product_id: '37500001',
    sku_id: 'S1',
    quantity: 1,
    buyer_paid_amount: 28.9,
    status: 'received',
    error_message: null,
    fulfilled_at: null,
    created_at: '2024-06-24T09:10:00Z',
    supplier_order: null,
  },
];

type Tab = 'listings' | 'orders';

export default function Fulfillment() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>('listings');
  const [showForm, setShowForm] = useState(false);

  const { data: listingsData } = useQuery({
    queryKey: ['fulfillment', 'listings'],
    queryFn: () => fulfillmentApi.listListings().then((r) => r.data),
  });

  const { data: ordersData } = useQuery({
    queryKey: ['fulfillment', 'orders'],
    queryFn: () => fulfillmentApi.listOrders().then((r) => r.data),
  });

  const { data: statsData } = useQuery({
    queryKey: ['fulfillment', 'stats'],
    queryFn: () => fulfillmentApi.getStats().then((r) => r.data),
  });

  const fulfillMutation = useMutation({
    mutationFn: (id: string) => fulfillmentApi.fulfillOrder(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['fulfillment', 'orders'] }),
  });

  const listings =
    listingsData && listingsData.length > 0 ? listingsData : mockListings;
  const orders = ordersData && ordersData.length > 0 ? ordersData : mockOrders;

  const listedCount =
    statsData?.listings_by_status?.listed ??
    listings.filter((l) => l.status === 'listed').length;
  const matchingCount =
    (statsData?.listings_by_status?.matching ?? 0) +
      (statsData?.listings_by_status?.matched ?? 0) ||
    listings.filter((l) => l.status === 'matching' || l.status === 'matched').length;
  const totalOrders =
    (statsData
      ? Object.values(statsData.orders_by_status).reduce((a, b) => a + b, 0)
      : 0) || orders.length;
  const shippedCount =
    ((statsData?.orders_by_status?.shipped ?? 0) +
      (statsData?.orders_by_status?.delivered ?? 0)) ||
    orders.filter((o) => o.status === 'shipped' || o.status === 'delivered').length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Truck className="w-6 h-6 text-brand-primary" />
            {t('fulfillment.title')}
          </h1>
          <p className="text-sm text-gray-500 mt-1">{t('fulfillment.subtitle')}</p>
        </div>
        <button
          className="btn-primary flex items-center gap-2 text-sm"
          onClick={() => setShowForm(true)}
        >
          <Plus className="w-4 h-4" />
          {t('fulfillment.newSourcing')}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<Store className="w-5 h-5 text-green-600" />}
          label={t('fulfillment.statListed')}
          value={listedCount}
        />
        <StatCard
          icon={<Package className="w-5 h-5 text-blue-600" />}
          label={t('fulfillment.statMatching')}
          value={matchingCount}
        />
        <StatCard
          icon={<ShoppingCart className="w-5 h-5 text-indigo-600" />}
          label={t('fulfillment.statOrders')}
          value={totalOrders}
        />
        <StatCard
          icon={<CheckCircle2 className="w-5 h-5 text-purple-600" />}
          label={t('fulfillment.statShipped')}
          value={shippedCount}
        />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b">
        <TabButton
          active={tab === 'listings'}
          onClick={() => setTab('listings')}
          label={t('fulfillment.tabListings')}
        />
        <TabButton
          active={tab === 'orders'}
          onClick={() => setTab('orders')}
          label={t('fulfillment.tabOrders')}
        />
      </div>

      {tab === 'listings' ? (
        <ListingsTable listings={listings} />
      ) : (
        <OrdersTable
          orders={orders}
          onFulfill={(id) => fulfillMutation.mutate(id)}
          fulfillingId={fulfillMutation.isPending ? fulfillMutation.variables : null}
        />
      )}

      {showForm && <SourceListingModal onClose={() => setShowForm(false)} />}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="card p-4 flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center">
        {icon}
      </div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
        active
          ? 'border-brand-primary text-gray-900'
          : 'border-transparent text-gray-500 hover:text-gray-800'
      }`}
    >
      {label}
    </button>
  );
}

function ListingsTable({ listings }: { listings: FulfillmentListing[] }) {
  const { t } = useLanguage();

  if (listings.length === 0) {
    return (
      <div className="card p-10 text-center text-sm text-gray-500">
        {t('fulfillment.noListings')}
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-gray-50/50">
            <Th>{t('fulfillment.product')}</Th>
            <Th>{t('fulfillment.supplier')}</Th>
            <Th>{t('fulfillment.matchScore')}</Th>
            <Th>{t('fulfillment.wholesale')}</Th>
            <Th>{t('fulfillment.landedCost')}</Th>
            <Th>{t('fulfillment.sellPrice')}</Th>
            <Th>{t('fulfillment.margin')}</Th>
            <Th>{t('fulfillment.status')}</Th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {listings.map((l) => (
            <tr key={l.id} className="hover:bg-gray-50/50 transition-colors">
              <td className="px-5 py-3">
                <span className="text-sm font-medium text-gray-900">{l.title}</span>
                <p className="text-xs text-gray-400">{l.category}</p>
              </td>
              <td className="px-5 py-3">
                {l.supplier_name ? (
                  <a
                    href={l.supplier_url || '#'}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-gray-600 hover:text-brand-primary inline-flex items-center gap-1"
                  >
                    {l.supplier_name}
                    {l.supplier_url && <ExternalLink className="w-3 h-3" />}
                  </a>
                ) : (
                  <span className="text-sm text-gray-300">—</span>
                )}
              </td>
              <td className="px-5 py-3">
                <span className="text-sm text-gray-900">
                  {l.match_score ? `${(l.match_score * 100).toFixed(0)}%` : '—'}
                </span>
              </td>
              <td className="px-5 py-3 text-sm text-gray-600">
                {l.wholesale_price ? `¥${l.wholesale_price.toFixed(2)}` : '—'}
              </td>
              <td className="px-5 py-3 text-sm text-gray-600">
                {l.landed_cost ? `¥${l.landed_cost.toFixed(2)}` : '—'}
              </td>
              <td className="px-5 py-3 text-sm font-medium text-gray-900">
                {l.sell_price ? `¥${l.sell_price.toFixed(2)}` : '—'}
              </td>
              <td className="px-5 py-3">
                <span
                  className={`text-sm font-medium ${
                    l.achieved_margin >= l.target_margin
                      ? 'text-green-600'
                      : 'text-gray-400'
                  }`}
                >
                  {l.achieved_margin ? `${(l.achieved_margin * 100).toFixed(1)}%` : '—'}
                </span>
              </td>
              <td className="px-5 py-3">
                <StatusBadge status={l.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OrdersTable({
  orders,
  onFulfill,
  fulfillingId,
}: {
  orders: FulfillmentOrder[];
  onFulfill: (id: string) => void;
  fulfillingId: string | null;
}) {
  const { t } = useLanguage();

  if (orders.length === 0) {
    return (
      <div className="card p-10 text-center text-sm text-gray-500">
        {t('fulfillment.noOrders')}
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-gray-50/50">
            <Th>{t('fulfillment.orderNo')}</Th>
            <Th>{t('fulfillment.qty')}</Th>
            <Th>{t('fulfillment.paid')}</Th>
            <Th>{t('fulfillment.status')}</Th>
            <Th>{t('fulfillment.alibabaOrder')}</Th>
            <Th>{t('fulfillment.tracking')}</Th>
            <Th>{t('fulfillment.actions')}</Th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {orders.map((o) => {
            const canFulfill =
              o.status === 'received' || o.status === 'fulfill_failed';
            return (
              <tr key={o.id} className="hover:bg-gray-50/50 transition-colors">
                <td className="px-5 py-3">
                  <span className="text-sm font-medium text-gray-900">
                    {o.douyin_order_id}
                  </span>
                </td>
                <td className="px-5 py-3 text-sm text-gray-600">{o.quantity}</td>
                <td className="px-5 py-3 text-sm font-medium text-gray-900">
                  ¥{o.buyer_paid_amount.toFixed(2)}
                </td>
                <td className="px-5 py-3">
                  <StatusBadge status={o.status} />
                </td>
                <td className="px-5 py-3 text-sm text-gray-600">
                  {o.supplier_order?.alibaba_order_id ?? '—'}
                </td>
                <td className="px-5 py-3 text-sm text-gray-600">
                  {o.supplier_order?.tracking_no ? (
                    <span>
                      {o.supplier_order.tracking_no}
                      {o.supplier_order.logistics_company && (
                        <span className="text-xs text-gray-400 ml-1">
                          ({o.supplier_order.logistics_company})
                        </span>
                      )}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-5 py-3">
                  {canFulfill && (
                    <button
                      className="btn-primary text-xs py-1.5 px-3"
                      onClick={() => onFulfill(o.id)}
                      disabled={fulfillingId === o.id}
                    >
                      {fulfillingId === o.id
                        ? t('fulfillment.fulfilling')
                        : t('fulfillment.fulfill')}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
      {children}
    </th>
  );
}

function SourceListingModal({ onClose }: { onClose: () => void }) {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    title: '',
    category: '',
    image_url: '',
    description: '',
    auto_publish: false,
  });
  const [result, setResult] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      fulfillmentApi
        .sourceAndList({
          title: form.title,
          category: form.category || undefined,
          image_url: form.image_url || undefined,
          description: form.description || undefined,
          auto_publish: form.auto_publish,
          async_mode: true,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      setResult(data.task_id ? `已提交，任务ID: ${data.task_id}` : '已提交');
      queryClient.invalidateQueries({ queryKey: ['fulfillment', 'listings'] });
    },
    onError: () => setResult('提交失败，请检查后端配置'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            {t('fulfillment.formTitle')}
          </h2>
          <p className="text-sm text-gray-500 mt-1">{t('fulfillment.subtitle')}</p>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('fulfillment.fieldTitle')}
            </label>
            <input
              type="text"
              className="input-field"
              placeholder={t('fulfillment.fieldTitlePlaceholder')}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('fulfillment.fieldCategory')}
            </label>
            <input
              type="text"
              className="input-field"
              value={form.category}
              onChange={(e) => setForm({ ...form, category: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('fulfillment.fieldImage')}
            </label>
            <input
              type="text"
              className="input-field"
              placeholder="https://..."
              value={form.image_url}
              onChange={(e) => setForm({ ...form, image_url: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('fulfillment.fieldDescription')}
            </label>
            <textarea
              className="input-field"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.auto_publish}
              onChange={(e) => setForm({ ...form, auto_publish: e.target.checked })}
            />
            {t('fulfillment.autoPublish')}
          </label>
          {result && (
            <div className="text-sm text-gray-600 bg-gray-50 rounded-lg px-3 py-2">
              {result}
            </div>
          )}
        </div>
        <div className="p-6 border-t flex items-center justify-end gap-3">
          <button className="btn-secondary" onClick={onClose}>
            {t('fulfillment.cancel')}
          </button>
          <button
            className="btn-primary"
            onClick={() => mutation.mutate()}
            disabled={!form.title || mutation.isPending}
          >
            {mutation.isPending ? t('fulfillment.sourcing') : t('fulfillment.submit')}
          </button>
        </div>
      </div>
    </div>
  );
}
