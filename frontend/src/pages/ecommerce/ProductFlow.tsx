import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Typography, Card, Space } from 'antd';
import FlowNode from '@/components/flow/FlowNode';
import NodeDrawer from '@/components/flow/NodeDrawer';
import type { FlowNodeData } from '@/types';

const { Title, Text } = Typography;

const nodeTypes = { custom: FlowNode };

const flowSteps: FlowNodeData[] = [
  { id: '1', label: '选品发现', status: 'completed', timestamp: '2024-05-01 10:00', description: '通过数据分析发现潜力品类，筛选出高需求低竞争的商品。' },
  { id: '2', label: '货源匹配', status: 'completed', timestamp: '2024-05-02 14:00', description: '在1688、拼多多等平台匹配优质供应商，比较价格和质量。' },
  { id: '3', label: '成本核算', status: 'completed', timestamp: '2024-05-03 09:30', description: '计算商品成本、物流费、平台佣金、广告预算等全链路成本。' },
  { id: '4', label: '样品确认', status: 'completed', timestamp: '2024-05-05 16:00', description: '下单样品，验证质量、尺寸、颜色等是否符合预期。' },
  { id: '5', label: '素材生成', status: 'running', timestamp: '2024-05-07 11:00', description: 'AI 生成商品主图、视频脚本、详情页素材。' },
  { id: '6', label: '素材审核', status: 'pending', timestamp: '', description: '人工审核 AI 生成的素材质量，确保合规。' },
  { id: '7', label: '定价策略', status: 'pending', timestamp: '', description: '基于成本和市场竞品分析制定售价策略。' },
  { id: '8', label: '商品上架', status: 'pending', timestamp: '', description: '将商品信息和素材上传到各销售平台。' },
  { id: '9', label: '广告投放', status: 'pending', timestamp: '', description: '配置广告计划，设定投放预算和目标受众。' },
  { id: '10', label: '订单产生', status: 'pending', timestamp: '', description: '用户下单购买，系统自动接收并处理订单。' },
  { id: '11', label: '自动发货', status: 'pending', timestamp: '', description: '系统自动向供应商下采购单并安排发货。' },
  { id: '12', label: '物流跟踪', status: 'pending', timestamp: '', description: '实时跟踪包裹运输状态，异常自动预警。' },
  { id: '13', label: '签收确认', status: 'pending', timestamp: '', description: '买家签收后确认收货，触发资金结算。' },
  { id: '14', label: '评价跟进', status: 'pending', timestamp: '', description: '自动邀请买家评价，监控差评并及时处理。' },
  { id: '15', label: '售后处理', status: 'pending', timestamp: '', description: '处理退货退款、客诉等售后问题。' },
  { id: '16', label: '数据归档', status: 'pending', timestamp: '', description: '归档全链路数据，生成经营分析报表。' },
];

function buildNodes(steps: FlowNodeData[]): Node[] {
  const cols = 4;
  const xGap = 280;
  const yGap = 140;

  return steps.map((step, index) => {
    const row = Math.floor(index / cols);
    const col = row % 2 === 0 ? index % cols : cols - 1 - (index % cols);
    return {
      id: step.id,
      type: 'custom',
      position: { x: col * xGap + 50, y: row * yGap + 50 },
      data: step,
    };
  });
}

function buildEdges(steps: FlowNodeData[]): Edge[] {
  return steps.slice(0, -1).map((step, index) => ({
    id: `e${step.id}-${steps[index + 1].id}`,
    source: step.id,
    target: steps[index + 1].id,
    animated: step.status === 'running',
    style: {
      stroke: step.status === 'completed' ? '#52c41a' : '#d9d9d9',
      strokeWidth: 2,
    },
  }));
}

export default function ProductFlow() {
  const { id } = useParams<{ id: string }>();
  const [nodes, , onNodesChange] = useNodesState(buildNodes(flowSteps));
  const [edges, , onEdgesChange] = useEdgesState(buildEdges(flowSteps));
  const [selectedNode, setSelectedNode] = useState<FlowNodeData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const data = node.data as unknown as FlowNodeData;
    setSelectedNode(data);
    setDrawerOpen(true);
  }, []);

  const navigateNode = useCallback(
    (direction: 'prev' | 'next') => {
      if (!selectedNode) return;
      const currentIndex = flowSteps.findIndex((s) => s.id === selectedNode.id);
      const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;
      if (nextIndex >= 0 && nextIndex < flowSteps.length) {
        setSelectedNode(flowSteps[nextIndex]);
      }
    },
    [selectedNode]
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!drawerOpen) return;
      if (e.key === 'ArrowRight') {
        navigateNode('next');
      } else if (e.key === 'ArrowLeft') {
        navigateNode('prev');
      } else if (e.key === 'Escape') {
        setDrawerOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [drawerOpen, navigateNode]);

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>
          商品全链路 - {id === 'default' ? '流程总览' : `商品 #${id}`}
        </Title>
        <Text type="secondary">点击节点查看详情，使用 ← → 键切换节点</Text>
      </div>

      <Card
        style={{ flex: 1, overflow: 'hidden' }}
        bodyStyle={{ padding: 0, height: '100%' }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
        >
          <Background color="#f0f0f0" gap={20} />
          <Controls />
          <MiniMap
            nodeStrokeColor="#1677ff"
            nodeColor={(n) => {
              const data = n.data as unknown as FlowNodeData;
              if (data.status === 'completed') return '#52c41a';
              if (data.status === 'running') return '#1677ff';
              return '#d9d9d9';
            }}
          />
          <Panel position="top-right">
            <Card size="small" style={{ opacity: 0.9 }}>
              <Space direction="vertical" size={2}>
                <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#52c41a' }} /> <Text style={{ fontSize: 12 }}>已完成</Text></Space>
                <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#1677ff' }} /> <Text style={{ fontSize: 12 }}>进行中</Text></Space>
                <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#d9d9d9' }} /> <Text style={{ fontSize: 12 }}>待处理</Text></Space>
              </Space>
            </Card>
          </Panel>
        </ReactFlow>
      </Card>

      <NodeDrawer
        open={drawerOpen}
        node={selectedNode}
        onClose={() => setDrawerOpen(false)}
        onNavigate={navigateNode}
      />
    </div>
  );
}
