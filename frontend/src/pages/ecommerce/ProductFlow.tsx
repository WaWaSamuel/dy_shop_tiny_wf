import { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Typography, Card, Space, Row, Col, Tag, Button, Empty, Avatar } from 'antd';
import FlowNode from '@/components/flow/FlowNode';
import NodeDrawer from '@/components/flow/NodeDrawer';
import type { FlowNodeData, ImportedCatalogItem, WorkflowAsset, WorkflowStageAsset } from '@/types';
import { getStoredCatalog } from '@/services/douzhangguiCatalog';
import { buildCatalogKey, buildWorkflowAssetFromCatalog, getStoredWorkflowAssets } from '@/services/workflowAssets';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Text } = Typography;

const nodeTypes = { custom: FlowNode };

const demoCatalogItems: ImportedCatalogItem[] = [
  {
    id: 'hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    catalogKey: 'hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    workflowAssetId: 'wf:hachiware 数码店::bt-ear-001::无线蓝牙耳机 tws 入耳式',
    name: '无线蓝牙耳机 TWS 入耳式',
    sku: 'BT-EAR-001',
    shopName: 'Hachiware 数码店',
    category: '数码配件',
    supplier: '深圳市通达电子有限公司',
    source: '抖掌柜 Excel 示例',
    price: 29.99,
    cost: 8.5,
    stock: 520,
    statusText: '已上架',
    listingStatus: 'active',
    updatedAt: '2026-06-26 09:10',
    raw: {},
  },
  {
    id: 'usagi beauty::led-mir-002::led 智能化妆镜带灯',
    catalogKey: 'usagi beauty::led-mir-002::led 智能化妆镜带灯',
    workflowAssetId: 'wf:usagi beauty::led-mir-002::led 智能化妆镜带灯',
    name: 'LED 智能化妆镜带灯',
    sku: 'LED-MIR-002',
    shopName: 'Usagi Beauty',
    category: '美妆工具',
    supplier: '义乌市美亮电器厂',
    source: '抖掌柜 Excel 示例',
    price: 15.99,
    cost: 4.2,
    stock: 380,
    statusText: '待上架',
    listingStatus: 'pending',
    updatedAt: '2026-06-26 09:30',
    raw: {},
  },
];

function stageToNode(step: WorkflowStageAsset, index: number): FlowNodeData {
  const warningCount =
    step.logs.filter((log) => log.type === 'warning' || log.type === 'error').length;

  return {
    id: step.key,
    label: step.label,
    status: step.status,
    timestamp: step.timestamp,
    description: step.description,
    logs: step.logs,
    relatedLinks: step.relatedLinks,
    metadata: step.metadata,
    sequence: index + 1,
    warningCount,
  };
}

function buildNodes(steps: WorkflowStageAsset[]): Node[] {
  const cols = 4;
  const xGap = 280;
  const yGap = 140;

  return steps.map((step, index) => {
    const row = Math.floor(index / cols);
    const col = row % 2 === 0 ? index % cols : cols - 1 - (index % cols);
    return {
      id: step.key,
      type: 'custom',
      position: { x: col * xGap + 50, y: row * yGap + 50 },
      data: stageToNode(step, index),
    };
  });
}

function buildEdges(steps: WorkflowStageAsset[]): Edge[] {
  return steps.slice(0, -1).map((step, index) => ({
    id: `e${step.key}-${steps[index + 1].key}`,
    source: step.key,
    target: steps[index + 1].key,
    animated: step.status === 'running',
    style: {
      stroke: step.status === 'completed' ? '#52c41a' : '#d9d9d9',
      strokeWidth: 2,
    },
  }));
}

export default function ProductFlow() {
  const { id } = useParams();
  const decodedId = useMemo(() => decodeURIComponent(id || ''), [id]);

  const catalogItems = useMemo(() => {
    const stored = getStoredCatalog();
    return stored.length ? stored : demoCatalogItems;
  }, []);

  const workflowAssets = useMemo(() => {
    const stored = getStoredWorkflowAssets();
    return stored.length ? stored : catalogItems.map((item) => buildWorkflowAssetFromCatalog(item));
  }, [catalogItems]);

  const selectedCatalogItem = useMemo(() => {
    const directMatch = catalogItems.find((item) => (item.catalogKey || buildCatalogKey(item)) === decodedId);
    if (directMatch) return directMatch;
    return catalogItems.find((item) => item.id === decodedId) || catalogItems[0] || null;
  }, [catalogItems, decodedId]);

  const selectedAsset = useMemo<WorkflowAsset | null>(() => {
    if (!selectedCatalogItem) return null;
    const catalogKey = selectedCatalogItem.catalogKey || buildCatalogKey(selectedCatalogItem);
    return workflowAssets.find((asset) => asset.catalogKey === catalogKey) || buildWorkflowAssetFromCatalog(selectedCatalogItem);
  }, [selectedCatalogItem, workflowAssets]);

  const flowStages = selectedAsset?.stages || [];
  const nodes = useMemo(() => buildNodes(flowStages), [flowStages]);
  const edges = useMemo(() => buildEdges(flowStages), [flowStages]);
  const [selectedNode, setSelectedNode] = useState<FlowNodeData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    setSelectedNode(null);
    setDrawerOpen(false);
  }, [selectedAsset?.id]);

  const handleNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    const data = node.data as unknown as FlowNodeData;
    setSelectedNode(data);
    setDrawerOpen(true);
  }, []);

  const navigateNode = useCallback(
    (direction: 'prev' | 'next') => {
      if (!selectedNode) return;
      const currentIndex = flowStages.findIndex((s) => s.key === selectedNode.id);
      const nextIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;
      if (nextIndex >= 0 && nextIndex < flowStages.length) {
        setSelectedNode(stageToNode(flowStages[nextIndex], nextIndex));
      }
    },
    [flowStages, selectedNode]
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

  if (!selectedCatalogItem || !selectedAsset) {
    return (
      <Card className="surface-card">
        <Empty
          description="没有找到对应货品的工作流资产"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" onClick={() => window.location.assign('/project/ecommerce/products')}>
            返回货盘
          </Button>
        </Empty>
      </Card>
    );
  }

  const completedCount = flowStages.filter((stage) => stage.status === 'completed').length;
  const currentStageLabel = flowStages.find((stage) => stage.key === selectedAsset.currentStageKey)?.label || '未开始';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Card className="surface-card">
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} lg={15}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              <Space size={[8, 8]} wrap>
                <Tag color="blue">{selectedAsset.workflowName}</Tag>
                <Tag color="default">{selectedAsset.workflowVersion}</Tag>
                <Tag color={selectedCatalogItem.listingStatus === 'active' ? 'green' : 'orange'}>
                  {selectedCatalogItem.statusText}
                </Tag>
              </Space>
              <div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{selectedCatalogItem.name}</div>
                <Text type="secondary">
                  {selectedCatalogItem.shopName} · {selectedCatalogItem.sku} · {selectedCatalogItem.category}
                </Text>
              </div>
              <Text type="secondary" style={{ lineHeight: 1.7 }}>{selectedAsset.summary}</Text>
              <Space size={[8, 8]} wrap>
                <Tag>当前节点：{currentStageLabel}</Tag>
                <Tag>已完成：{completedCount}/{flowStages.length}</Tag>
                <Tag>供应商：{selectedCatalogItem.supplier}</Tag>
                <Tag>更新时间：{selectedCatalogItem.updatedAt}</Tag>
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={9}>
            <Card size="small" className="result-mini-card" bordered={false}>
              <Space align="start" size={12}>
                <Avatar
                  shape="square"
                  size={56}
                  src={stickers.dashboard.ecommerce}
                  style={{ borderRadius: 20, background: 'linear-gradient(135deg, rgba(255,238,244,0.98), rgba(242,249,255,0.96))', padding: 8 }}
                />
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Text strong>轨迹摘要</Text>
                  <Text type="secondary" style={{ lineHeight: 1.65 }}>
                    这是一份和货品绑定的结果轨迹，用来回看当前走到了哪一步、哪里需要继续跟进。
                  </Text>
                  <div className="overview-action-grid" style={{ gridTemplateColumns: '1fr' }}>
                    <a className="result-nav-button result-nav-button--primary" href="/project/ecommerce/products">
                      <img src={stickers.actions.prev} alt="" />
                      <span>返回货盘结果页</span>
                    </a>
                  </div>
                  <Text type="secondary">资产ID：{selectedAsset.id}</Text>
                </Space>
              </Space>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.workflow} alt="当前阶段" size="lg" />
              </div>
              <div>
                <Text type="secondary">当前阶段</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{currentStageLabel}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.pending} alt="待跟进节点" size="lg" />
              </div>
              <div>
                <Text type="secondary">待跟进节点</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{Math.max(flowStages.length - completedCount, 0)}</div>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card className="stats-glass-card">
            <div className="metric-strip">
              <div className="metric-badge">
                <StickerIcon src={stickers.metrics.imported} alt="结果完成度" size="lg" />
              </div>
              <div>
                <Text type="secondary">结果完成度</Text>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{Math.round((completedCount / Math.max(flowStages.length, 1)) * 100)}%</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      <div style={{ height: 'calc(100vh - 320px)', minHeight: 560, display: 'flex', flexDirection: 'column' }}>
        <Card style={{ flex: 1, overflow: 'hidden' }} bodyStyle={{ padding: 0, height: '100%' }}>
          <ReactFlow
            key={selectedAsset.id}
            nodes={nodes}
            edges={edges}
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
                if (data.status === 'failed') return '#ff4d4f';
                return '#d9d9d9';
              }}
            />
            <Panel position="top-right">
              <Card size="small" style={{ opacity: 0.96 }}>
                <Space direction="vertical" size={4}>
                  <Text style={{ fontSize: 12 }}>当前货品工作流</Text>
                  <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#52c41a' }} /> <Text style={{ fontSize: 12 }}>已完成</Text></Space>
                  <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#1677ff' }} /> <Text style={{ fontSize: 12 }}>进行中</Text></Space>
                  <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#d9d9d9' }} /> <Text style={{ fontSize: 12 }}>待处理</Text></Space>
                  <Space><div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ff4d4f' }} /> <Text style={{ fontSize: 12 }}>失败</Text></Space>
                </Space>
              </Card>
            </Panel>
          </ReactFlow>
        </Card>
      </div>

      <NodeDrawer
        open={drawerOpen}
        node={selectedNode}
        onClose={() => setDrawerOpen(false)}
        onNavigate={navigateNode}
      />
    </div>
  );
}
