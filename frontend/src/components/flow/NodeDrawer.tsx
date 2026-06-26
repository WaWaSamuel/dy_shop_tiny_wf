import {
  Drawer,
  Typography,
  Space,
  Tag,
  Descriptions,
  Timeline,
  Button,
  Divider,
  Empty,
} from 'antd';
import type { FlowLog, FlowNodeData } from '@/types';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Title, Text, Paragraph } = Typography;

interface NodeDrawerProps {
  open: boolean;
  node: FlowNodeData | null;
  onClose: () => void;
  onNavigate: (direction: 'prev' | 'next') => void;
}

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  completed: { label: '已完成', color: 'success', icon: <StickerIcon src={stickers.statusCompleted} alt="已完成" size="xs" /> },
  running: { label: '进行中', color: 'processing', icon: <StickerIcon src={stickers.statusRunning} alt="进行中" size="xs" /> },
  pending: { label: '待处理', color: 'default', icon: <StickerIcon src={stickers.statusPending} alt="待处理" size="xs" /> },
  failed: { label: '失败', color: 'error', icon: <StickerIcon src={stickers.statusFailed} alt="失败" size="xs" /> },
};

const mockLogs: FlowLog[] = [
  { id: 'log-1', time: '2024-06-01 10:00:00', content: '节点创建', type: 'info' as const },
  { id: 'log-2', time: '2024-06-01 10:05:00', content: '开始执行', type: 'info' as const },
  { id: 'log-3', time: '2024-06-01 10:30:00', content: '处理完成，结果正常', type: 'success' as const },
];

const mockRelatedLinks = [
  { title: '供应商详情', url: '#' },
  { title: '商品详情页', url: '#' },
  { title: '物流追踪', url: '#' },
];

export default function NodeDrawer({ open, node, onClose, onNavigate }: NodeDrawerProps) {
  if (!node) return null;

  const status = statusConfig[node.status] || statusConfig.pending;

  return (
    <Drawer
      title={
        <Space>
          <span>{node.label}</span>
          <Tag color={status.color} icon={status.icon}>
            {status.label}
          </Tag>
        </Space>
      }
      placement="right"
      width={480}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Button icon={<StickerIcon src={stickers.actionPrev} alt="上一步" size="sm" />} size="small" onClick={() => onNavigate('prev')}>
            上一步
          </Button>
          <Button icon={<StickerIcon src={stickers.actionNext} alt="下一步" size="sm" />} size="small" onClick={() => onNavigate('next')}>
            下一步
          </Button>
        </Space>
      }
    >
      {/* Basic Info Section */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 12 }}>
          基本信息
        </Title>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="节点名称">{node.label}</Descriptions.Item>
          <Descriptions.Item label="节点ID">{node.id}</Descriptions.Item>
          <Descriptions.Item label="当前状态">
            <Tag color={status.color} icon={status.icon}>{status.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="执行时间">
            {node.timestamp || '尚未执行'}
          </Descriptions.Item>
        </Descriptions>
      </div>

      {/* Core Data Section */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 12 }}>
          核心数据
        </Title>
        <Paragraph type="secondary">
          {node.description || '暂无详细描述'}
        </Paragraph>
      </div>

      <Divider />

      {/* Logs Section */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 12 }}>
          执行日志
        </Title>
        {node.status === 'pending' ? (
          <Empty description="该节点尚未执行" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <Timeline
            items={mockLogs.map((log) => ({
              color: log.type === 'success' ? 'green' : log.type === 'error' ? 'red' : 'blue',
              children: (
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>{log.time}</Text>
                  <div><Text style={{ fontSize: 13 }}>{log.content}</Text></div>
                </div>
              ),
            }))}
          />
        )}
      </div>

      <Divider />

      {/* Related Links Section */}
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 12 }}>
          关联信息
        </Title>
        <Space direction="vertical" style={{ width: '100%' }}>
          {mockRelatedLinks.map((link) => (
            <Button
              key={link.title}
              type="link"
              icon={<StickerIcon src={stickers.actionLink} alt="关联链接" size="sm" />}
              style={{ padding: 0 }}
              href={link.url}
            >
              {link.title}
            </Button>
          ))}
        </Space>
      </div>

      <Divider />

      {/* Action Buttons */}
      <div>
        <Title level={5} style={{ marginBottom: 12 }}>
          操作
        </Title>
        <Space wrap>
          {node.status === 'pending' && (
            <Button type="primary" icon={<StickerIcon src={stickers.actionPlay} alt="开始执行" size="sm" />}>
              开始执行
            </Button>
          )}
          {node.status === 'running' && (
            <Button danger icon={<StickerIcon src={stickers.actionPause} alt="暂停" size="sm" />}>
              暂停
            </Button>
          )}
          {node.status === 'completed' && (
            <Button icon={<StickerIcon src={stickers.actionRetry} alt="重新执行" size="sm" />}>
              重新执行
            </Button>
          )}
          {node.status === 'failed' && (
            <Button type="primary" danger icon={<StickerIcon src={stickers.actionRetry} alt="重试" size="sm" />}>
              重试
            </Button>
          )}
          <Button>查看详情</Button>
        </Space>
      </div>
    </Drawer>
  );
}
