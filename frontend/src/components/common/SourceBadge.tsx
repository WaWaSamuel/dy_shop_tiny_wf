import { Tag } from 'antd';

const sourceConfig: Record<string, { label: string; color: string; icon: string }> = {
  alibaba_1688: { label: '1688', color: '#ff6a00', icon: '🏭' },
  pinduoduo: { label: '拼多多', color: '#e02e24', icon: '🛍️' },
  taobao: { label: '淘宝', color: '#ff5000', icon: '🛒' },
  direct_factory: { label: '工厂直联', color: '#1677ff', icon: '🏗️' },
  tiktok: { label: 'TikTok', color: '#000000', icon: '🎵' },
  temu: { label: 'Temu', color: '#f26b2a', icon: '📦' },
};

interface SourceBadgeProps {
  source: string;
  size?: 'small' | 'default';
}

export default function SourceBadge({ source, size = 'small' }: SourceBadgeProps) {
  const config = sourceConfig[source] || { label: source, color: '#999', icon: '📌' };

  return (
    <Tag
      color={config.color}
      style={{
        borderRadius: 4,
        fontSize: size === 'small' ? 11 : 12,
        lineHeight: size === 'small' ? '18px' : '22px',
        padding: size === 'small' ? '0 4px' : '0 8px',
      }}
    >
      {config.icon} {config.label}
    </Tag>
  );
}
