import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Typography } from 'antd';
import type { FlowNodeData } from '@/types';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Text } = Typography;

const statusStyles: Record<string, { bg: string; border: string; color: string; icon: React.ReactNode }> = {
  completed: {
    bg: '#f6ffed',
    border: '#b7eb8f',
    color: '#52c41a',
    icon: <StickerIcon src={stickers.status.completed} alt="已完成" size="sm" />,
  },
  running: {
    bg: '#e6f4ff',
    border: '#91caff',
    color: '#1677ff',
    icon: <StickerIcon src={stickers.status.running} alt="进行中" size="sm" />,
  },
  pending: {
    bg: '#fafafa',
    border: '#d9d9d9',
    color: '#999',
    icon: <StickerIcon src={stickers.status.pending} alt="待处理" size="sm" />,
  },
  failed: {
    bg: '#fff2f0',
    border: '#ffccc7',
    color: '#ff4d4f',
    icon: <StickerIcon src={stickers.status.failed} alt="失败" size="sm" />,
  },
};

function FlowNode({ data }: NodeProps) {
  const nodeData = data as unknown as FlowNodeData;
  const style = statusStyles[nodeData.status] || statusStyles.pending;

  return (
    <div
      style={{
        padding: '12px 20px',
        borderRadius: 10,
        border: `2px solid ${style.border}`,
        background: style.bg,
        minWidth: 160,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: style.border }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {style.icon}
        <Text strong style={{ color: style.color, fontSize: 13 }}>
          {nodeData.sequence ? `${nodeData.sequence}. ` : ''}{nodeData.label}
        </Text>
      </div>
      {nodeData.warningCount ? (
        <Text style={{ fontSize: 10, display: 'block', marginTop: 4, color: '#fa8c16' }}>
          {nodeData.warningCount} 条异常提示
        </Text>
      ) : null}
      {nodeData.timestamp && (
        <Text type="secondary" style={{ fontSize: 10, display: 'block', marginTop: 4 }}>
          {nodeData.timestamp}
        </Text>
      )}
      <Handle type="source" position={Position.Right} style={{ background: style.border }} />
    </div>
  );
}

export default memo(FlowNode);
