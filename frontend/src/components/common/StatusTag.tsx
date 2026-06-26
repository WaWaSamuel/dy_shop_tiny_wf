import { Tag } from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  completed: { label: '已完成', color: 'success', icon: <StickerIcon src={stickers.status.completed} alt="已完成" size="xs" /> },
  running: { label: '进行中', color: 'processing', icon: <StickerIcon src={stickers.status.running} alt="进行中" size="xs" /> },
  pending: { label: '待处理', color: 'default', icon: <StickerIcon src={stickers.status.pending} alt="待处理" size="xs" /> },
  failed: { label: '失败', color: 'error', icon: <StickerIcon src={stickers.status.failed} alt="失败" size="xs" /> },
  warning: { label: '警告', color: 'warning', icon: <StickerIcon src={stickers.status.failed} alt="警告" size="xs" /> },
  active: { label: '在售', color: 'success', icon: <StickerIcon src={stickers.status.completed} alt="在售" size="xs" /> },
  inactive: { label: '下架', color: 'default', icon: <StickerIcon src={stickers.status.pending} alt="下架" size="xs" /> },
  out_of_stock: { label: '缺货', color: 'error', icon: <StickerIcon src={stickers.status.failed} alt="缺货" size="xs" /> },
  low_stock: { label: '低库存', color: 'warning', icon: <StickerIcon src={stickers.status.failed} alt="低库存" size="xs" /> },
  shipped: { label: '已发货', color: 'processing', icon: <StickerIcon src={stickers.actions.import} alt="已发货" size="xs" /> },
  delivered: { label: '已签收', color: 'success', icon: <StickerIcon src={stickers.status.completed} alt="已签收" size="xs" /> },
  cancelled: { label: '已取消', color: 'default', icon: <StickerIcon src={stickers.status.failed} alt="已取消" size="xs" /> },
};

interface StatusTagProps {
  status: string;
  showIcon?: boolean;
}

export default function StatusTag({ status, showIcon = true }: StatusTagProps) {
  const config = statusConfig[status] || { label: status, color: 'default', icon: null };

  return (
    <Tag color={config.color} icon={showIcon ? config.icon : undefined}>
      {config.label}
    </Tag>
  );
}
