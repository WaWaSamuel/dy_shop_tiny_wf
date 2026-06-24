import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Clock,
  Zap,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Send,
  Filter,
} from 'lucide-react';
import StatsCard from '../components/StatsCard';
import StatusBadge from '../components/StatusBadge';
import { feedbackApi, type FeedbackItem } from '../services/api';
import { useLanguage } from '../i18n';

type FilterStatus = '' | 'pending' | 'ai_drafted' | 'approved' | 'replied' | 'escalated';
type FilterType = '' | 'complaint' | 'inquiry' | 'review' | 'return_request';
type FilterSource = '' | 'douyin' | 'im' | 'phone';
type FilterUrgency = '' | 'low' | 'medium' | 'high' | 'critical';

// Mock data for display
const mockFeedback: FeedbackItem[] = [
  {
    id: '1',
    order_id: 'ORD-20240615-001',
    customer_name: 'Zhang Wei',
    content: 'The product color is different from what was shown in the pictures. I want a refund.',
    type: 'complaint',
    source: 'douyin',
    status: 'ai_drafted',
    urgency: 'high',
    sentiment_score: -0.7,
    ai_draft_reply:
      'Dear customer, we sincerely apologize for the color discrepancy. We would like to offer you a full refund or replacement. Please let us know your preference and we will process it immediately.',
    created_at: '2024-06-15T10:30:00Z',
    updated_at: '2024-06-15T10:31:00Z',
  },
  {
    id: '2',
    order_id: 'ORD-20240615-002',
    customer_name: 'Li Na',
    content: 'When will my order be shipped? I ordered 3 days ago.',
    type: 'inquiry',
    source: 'im',
    status: 'pending',
    urgency: 'medium',
    sentiment_score: -0.3,
    ai_draft_reply: null,
    created_at: '2024-06-15T11:15:00Z',
    updated_at: '2024-06-15T11:15:00Z',
  },
  {
    id: '3',
    order_id: 'ORD-20240614-018',
    customer_name: 'Wang Fang',
    content: 'Great quality! The dress fits perfectly. Will order again.',
    type: 'review',
    source: 'douyin',
    status: 'replied',
    urgency: 'low',
    sentiment_score: 0.9,
    ai_draft_reply: 'Thank you so much for your kind words! We are delighted you love the dress.',
    created_at: '2024-06-14T16:00:00Z',
    updated_at: '2024-06-14T16:05:00Z',
  },
  {
    id: '4',
    order_id: 'ORD-20240615-007',
    customer_name: 'Chen Ming',
    content: 'Product arrived damaged. The zipper is broken and there is a tear on the sleeve.',
    type: 'return_request',
    source: 'phone',
    status: 'escalated',
    urgency: 'critical',
    sentiment_score: -0.9,
    ai_draft_reply:
      'We are very sorry about the damaged item. We will arrange an immediate pickup and send a replacement within 24 hours at no extra cost.',
    created_at: '2024-06-15T09:00:00Z',
    updated_at: '2024-06-15T09:10:00Z',
  },
  {
    id: '5',
    order_id: 'ORD-20240615-012',
    customer_name: 'Liu Yang',
    content: 'Can I change the size from M to L? Haven not shipped yet.',
    type: 'inquiry',
    source: 'douyin',
    status: 'ai_drafted',
    urgency: 'low',
    sentiment_score: 0.1,
    ai_draft_reply:
      'Hi! We can change the size for you. We have updated your order to size L. It will ship today as scheduled.',
    created_at: '2024-06-15T12:00:00Z',
    updated_at: '2024-06-15T12:01:00Z',
  },
];

export default function Feedback() {
  const { t } = useLanguage();
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('');
  const [filterType, setFilterType] = useState<FilterType>('');
  const [filterSource, setFilterSource] = useState<FilterSource>('');
  const [filterUrgency, setFilterUrgency] = useState<FilterUrgency>('');

  const { data: statsData } = useQuery({
    queryKey: ['feedback-stats'],
    queryFn: () => feedbackApi.getStats().then((r) => r.data),
  });

  const { data: feedbackData } = useQuery({
    queryKey: ['feedback', filterStatus, filterType, filterSource, filterUrgency],
    queryFn: () =>
      feedbackApi
        .list({
          status: filterStatus || undefined,
          type: filterType || undefined,
          source: filterSource || undefined,
          urgency: filterUrgency || undefined,
        })
        .then((r) => r.data),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => feedbackApi.approve(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feedback'] }),
  });

  const items = feedbackData?.items ?? mockFeedback;
  const stats = statsData ?? {
    total_today: 42,
    pending_responses: 7,
    avg_response_time_min: 4.2,
    auto_reply_rate: 0.78,
    sentiment_breakdown: { positive: 45, neutral: 30, negative: 25 },
  };

  const filteredItems = items.filter((item) => {
    if (filterStatus && item.status !== filterStatus) return false;
    if (filterType && item.type !== filterType) return false;
    if (filterSource && item.source !== filterSource) return false;
    if (filterUrgency && item.urgency !== filterUrgency) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('feedback.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">
          {t('feedback.subtitle')}
        </p>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatsCard
          title={t('feedback.avgResponseTime')}
          value={`${stats.avg_response_time_min} min`}
          icon={Clock}
          iconColor="text-blue-600"
          iconBg="bg-blue-50"
        />
        <StatsCard
          title={t('feedback.autoReplyRate')}
          value={`${Math.round(stats.auto_reply_rate * 100)}%`}
          icon={Zap}
          iconColor="text-green-600"
          iconBg="bg-green-50"
        />
        <StatsCard
          title={t('feedback.positiveSentiment')}
          value={`${stats.sentiment_breakdown.positive}%`}
          icon={TrendingDown}
          iconColor="text-purple-600"
          iconBg="bg-purple-50"
        />
        <StatsCard
          title={t('feedback.pendingToday')}
          value={stats.pending_responses}
          icon={Clock}
          iconColor="text-amber-600"
          iconBg="bg-amber-50"
        />
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            className="input-field w-auto"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
          >
            <option value="">{t('filters.allStatus')}</option>
            <option value="pending">{t('status.pending')}</option>
            <option value="ai_drafted">{t('status.ai_drafted')}</option>
            <option value="approved">{t('status.approved')}</option>
            <option value="replied">{t('status.replied')}</option>
            <option value="escalated">{t('status.escalated')}</option>
          </select>
          <select
            className="input-field w-auto"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as FilterType)}
          >
            <option value="">{t('filters.allTypes')}</option>
            <option value="complaint">{t('status.complaint')}</option>
            <option value="inquiry">{t('status.inquiry')}</option>
            <option value="review">{t('status.review')}</option>
            <option value="return_request">{t('status.return_request')}</option>
          </select>
          <select
            className="input-field w-auto"
            value={filterSource}
            onChange={(e) => setFilterSource(e.target.value as FilterSource)}
          >
            <option value="">{t('filters.allSources')}</option>
            <option value="douyin">{t('status.douyin')}</option>
            <option value="im">{t('status.im')}</option>
            <option value="phone">{t('status.phone')}</option>
          </select>
          <select
            className="input-field w-auto"
            value={filterUrgency}
            onChange={(e) => setFilterUrgency(e.target.value as FilterUrgency)}
          >
            <option value="">{t('filters.allUrgency')}</option>
            <option value="low">{t('status.low')}</option>
            <option value="medium">{t('status.medium')}</option>
            <option value="high">{t('status.high')}</option>
            <option value="critical">{t('status.critical')}</option>
          </select>
        </div>
      </div>

      {/* Feedback Table */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-gray-50/50">
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.customer')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.type')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.source')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.status')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.urgency')}
              </th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wide px-5 py-3">
                {t('feedback.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filteredItems.map((item) => (
              <FeedbackRow
                key={item.id}
                item={item}
                isExpanded={expandedId === item.id}
                onToggle={() => setExpandedId(expandedId === item.id ? null : item.id)}
                onApprove={() => approveMutation.mutate(item.id)}
              />
            ))}
          </tbody>
        </table>
        {filteredItems.length === 0 && (
          <div className="text-center py-12 text-gray-400">{t('feedback.noItems')}</div>
        )}
      </div>
    </div>
  );
}

function FeedbackRow({
  item,
  isExpanded,
  onToggle,
  onApprove,
}: {
  item: FeedbackItem;
  isExpanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
}) {
  return (
    <>
      <tr
        className="hover:bg-gray-50/50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-5 py-3">
          <div>
            <p className="text-sm font-medium text-gray-900">{item.customer_name}</p>
            <p className="text-xs text-gray-400">{item.order_id}</p>
          </div>
        </td>
        <td className="px-5 py-3">
          <span className="text-sm text-gray-600 capitalize">
            {item.type.replace('_', ' ')}
          </span>
        </td>
        <td className="px-5 py-3">
          <span className="text-sm text-gray-600 capitalize">{item.source}</span>
        </td>
        <td className="px-5 py-3">
          <StatusBadge status={item.status} />
        </td>
        <td className="px-5 py-3">
          <StatusBadge status={item.urgency} />
        </td>
        <td className="px-5 py-3">
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={6} className="px-5 py-4 bg-gray-50/80">
            <div className="space-y-4 max-w-3xl">
              {/* Customer message */}
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase mb-1">
                  Customer Message
                </p>
                <p className="text-sm text-gray-700 bg-white p-3 rounded-lg border">
                  {item.content}
                </p>
              </div>

              {/* AI Draft Reply */}
              {item.ai_draft_reply && (
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase mb-1">
                    AI Draft Reply
                  </p>
                  <p className="text-sm text-gray-700 bg-blue-50 p-3 rounded-lg border border-blue-100">
                    {item.ai_draft_reply}
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-3">
                <button
                  className="btn-primary flex items-center gap-2 text-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    onApprove();
                  }}
                >
                  <CheckCircle className="w-4 h-4" />
                  Approve & Send
                </button>
                <button className="btn-secondary flex items-center gap-2 text-sm">
                  <Send className="w-4 h-4" />
                  Edit & Send
                </button>
                <button className="btn-outline flex items-center gap-2 text-sm">
                  <XCircle className="w-4 h-4" />
                  Reject
                </button>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
