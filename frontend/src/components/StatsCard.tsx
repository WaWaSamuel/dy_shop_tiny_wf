import { type LucideIcon } from 'lucide-react';

interface StatsCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: 'positive' | 'negative' | 'neutral';
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
}

export default function StatsCard({
  title,
  value,
  change,
  changeType = 'neutral',
  icon: Icon,
  iconColor = 'text-brand-primary',
  iconBg = 'bg-white/10',
}: StatsCardProps) {
  const changeColors = {
    positive: 'text-emerald-300',
    negative: 'text-rose-300',
    neutral: 'text-white/55',
  };

  return (
    <div className="card relative overflow-hidden p-5">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-white/12 to-transparent" />
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium uppercase tracking-[0.18em] text-white/50">{title}</p>
          <p className="text-3xl font-semibold text-white">{value}</p>
          {change && (
            <p className={`text-xs font-medium ${changeColors[changeType]}`}>
              {change}
            </p>
          )}
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-2xl border border-white/12 ${iconBg} shadow-[0_16px_34px_rgba(8,6,26,0.28)]`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
      </div>
    </div>
  );
}
