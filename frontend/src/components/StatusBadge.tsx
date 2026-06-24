import { useLanguage } from '../i18n';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const statusStyles: Record<string, { bg: string; text: string; dot: string }> = {
  // Feedback statuses
  pending: { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  ai_drafted: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
  approved: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
  replied: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },
  escalated: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
  rejected: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },

  // Product statuses
  draft: { bg: 'bg-gray-50', text: 'text-gray-700', dot: 'bg-gray-400' },
  uploading: { bg: 'bg-blue-50', text: 'text-blue-700', dot: 'bg-blue-500' },
  under_review: { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  online: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },

  // Design statuses
  queued: { bg: 'bg-gray-50', text: 'text-gray-700', dot: 'bg-gray-400' },
  generating: { bg: 'bg-purple-50', text: 'text-purple-700', dot: 'bg-purple-500' },
  completed: { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-500' },

  // Urgency
  low: { bg: 'bg-gray-50', text: 'text-gray-600', dot: 'bg-gray-400' },
  medium: { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-500' },
  high: { bg: 'bg-orange-50', text: 'text-orange-700', dot: 'bg-orange-500' },
  critical: { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500' },
};

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const { t } = useLanguage();
  const style = statusStyles[status] || statusStyles.pending;
  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm';

  const label = t(`status.${status}`);

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${style.bg} ${style.text} ${sizeClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      {label}
    </span>
  );
}
