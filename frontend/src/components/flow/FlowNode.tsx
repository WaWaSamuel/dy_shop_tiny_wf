import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Typography } from 'antd';
import {
  CheckCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { FlowNodeData } from '@/types';

const { Text } = Typography;

const statusStyles: Record<string, { bg: string; border: string; color: string; icon: React.ReactNode }> = {
  completed: {
    bg: '#f6ffed',
    border: '#b7eb8f',
    color: '#52c41a',
    icon: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
  },
  running: {
    bg: '#e6f4ff',
    border: '#91caff',
    color: '#1677ff',
    icon: <SyncOutlined spin style={{ color: '#1677ff' }} />,
  },
  pending: {
    bg: '#fafafa',
    border: '#d9d9d9',
    color: '#999',
    icon: <ClockCircleOutlined style={{ color: '#999' }} />,
  },
  failed: {
    bg: '#fff2f0',
    border: '#ffccc7',
    color: '#ff4d4f',
    icon: <ClockCircleOutlined style={{ color: '#ff4d4f' }} />,
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
          {nodeData.label}
        </Text>
      </div>
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
