import { useQuery } from '@tanstack/react-query';
import {
  MessageSquare,
  Clock,
  Package,
  TrendingUp,
  Activity,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import StatsCard from '../components/StatsCard';
import { feedbackApi } from '../services/api';
import { useLanguage } from '../i18n';

// Mock chart data
const feedbackTrend = [
  { date: 'Mon', count: 24, resolved: 20 },
  { date: 'Tue', count: 31, resolved: 28 },
  { date: 'Wed', count: 18, resolved: 17 },
  { date: 'Thu', count: 42, resolved: 35 },
  { date: 'Fri', count: 35, resolved: 33 },
  { date: 'Sat', count: 28, resolved: 26 },
  { date: 'Sun', count: 19, resolved: 18 },
];

const salesData = [
  { date: 'Mon', revenue: 4200, orders: 56 },
  { date: 'Tue', revenue: 5100, orders: 68 },
  { date: 'Wed', revenue: 3800, orders: 45 },
  { date: 'Thu', revenue: 6200, orders: 82 },
  { date: 'Fri', revenue: 5600, orders: 74 },
  { date: 'Sat', revenue: 7100, orders: 95 },
  { date: 'Sun', revenue: 4900, orders: 63 },
];

export default function Dashboard() {
  const { t, language } = useLanguage();
  const { data: stats } = useQuery({
    queryKey: ['feedback-stats'],
    queryFn: () => feedbackApi.getStats().then((r) => r.data),
  });

  const todayStr = format(new Date(), 'EEEE, MMMM d, yyyy');
  const recentActivity = [
    {
      id: '1',
      message:
        language === 'zh' ? '已自动回复客户投诉 #2847' : 'Auto-replied to customer complaint #2847',
      time: language === 'zh' ? '2 分钟前' : '2 min ago',
      icon: CheckCircle2,
      color: 'text-green-500',
    },
    {
      id: '2',
      message:
        language === 'zh'
          ? '商品 “Summer Dress V2” 已通过并上架'
          : 'Product "Summer Dress V2" approved and listed',
      time: language === 'zh' ? '15 分钟前' : '15 min ago',
      icon: Package,
      color: 'text-blue-500',
    },
    {
      id: '3',
      message:
        language === 'zh'
          ? '3 个新趋势商品已加入候选清单'
          : '3 new trending products added to shortlist',
      time: language === 'zh' ? '1 小时前' : '1 hour ago',
      icon: TrendingUp,
      color: 'text-purple-500',
    },
    {
      id: '4',
      message:
        language === 'zh'
          ? '有紧急反馈需要立即处理'
          : 'Critical feedback requires immediate attention',
      time: language === 'zh' ? '2 小时前' : '2 hours ago',
      icon: AlertCircle,
      color: 'text-red-500',
    },
    {
      id: '5',
      message:
        language === 'zh'
          ? '设计批次 #45 已完成，12 张图片可用'
          : 'Design batch #45 completed - 12 images ready',
      time: language === 'zh' ? '3 小时前' : '3 hours ago',
      icon: Activity,
      color: 'text-indigo-500',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{todayStr}</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title={t('dashboard.todayFeedback')}
          value={stats?.total_today ?? 42}
          change="+12% from yesterday"
          changeType="positive"
          icon={MessageSquare}
          iconColor="text-brand-primary"
          iconBg="bg-red-50"
        />
        <StatsCard
          title={t('dashboard.pendingResponses')}
          value={stats?.pending_responses ?? 7}
          change="3 critical"
          changeType="negative"
          icon={Clock}
          iconColor="text-amber-600"
          iconBg="bg-amber-50"
        />
        <StatsCard
          title={t('dashboard.newListings')}
          value={15}
          change="+5 today"
          changeType="positive"
          icon={Package}
          iconColor="text-blue-600"
          iconBg="bg-blue-50"
        />
        <StatsCard
          title={t('dashboard.trendAlerts')}
          value={8}
          change="3 high-potential"
          changeType="neutral"
          icon={TrendingUp}
          iconColor="text-purple-600"
          iconBg="bg-purple-50"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Feedback Trend */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            {t('dashboard.feedbackVolume')}
          </h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={feedbackTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#fe2c55"
                  fill="#fe2c5520"
                  strokeWidth={2}
                  name="Total"
                />
                <Area
                  type="monotone"
                  dataKey="resolved"
                  stroke="#22c55e"
                  fill="#22c55e15"
                  strokeWidth={2}
                  name="Resolved"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Sales Performance */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">
            {t('dashboard.salesPerformance')}
          </h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={salesData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                  name="Revenue (CNY)"
                />
                <Line
                  type="monotone"
                  dataKey="orders"
                  stroke="#25f4ee"
                  strokeWidth={2}
                  dot={false}
                  name="Orders"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card p-5">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">{t('dashboard.recentActivity')}</h3>
        <div className="space-y-3">
          {recentActivity.map((item) => (
            <div key={item.id} className="flex items-center gap-3 py-2">
              <div className="w-8 h-8 rounded-full bg-gray-50 flex items-center justify-center">
                <item.icon className={`w-4 h-4 ${item.color}`} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-700 truncate">{item.message}</p>
              </div>
              <span className="text-xs text-gray-400 whitespace-nowrap">{item.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
