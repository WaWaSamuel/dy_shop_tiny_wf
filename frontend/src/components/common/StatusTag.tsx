import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  completed: { label: '已完成', color: 'success', icon: <CheckCircleOutlined /> },
  running: { label: '进行中', color: 'processing', icon: <SyncOutlined spin /> },
  pending: { label: '待处理', color: 'default', icon: <ClockCircleOutlined /> },
  failed: { label: '失败', color: 'error', icon: <CloseCircleOutlined /> },
  warning: { label: '警告', color: 'warning', icon: <ExclamationCircleOutlined /> },
  active: { label: '在售', color: 'success', icon: <CheckCircleOutlined /> },
  inactive: { label: '下架', color: 'default', icon: <ClockCircleOutlined /> },
  out_of_stock: { label: '缺货', color: 'error', icon: <ExclamationCircleOutlined /> },
  low_stock: { label: '低库存', color: 'warning', icon: <ExclamationCircleOutlined /> },
  shipped: { label: '已发货', color: 'processing', icon: <SyncOutlined /> },
  delivered: { label: '已签收', color: 'success', icon: <CheckCircleOutlined /> },
  cancelled: { label: '已取消', color: 'default', icon: <CloseCircleOutlined /> },
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
