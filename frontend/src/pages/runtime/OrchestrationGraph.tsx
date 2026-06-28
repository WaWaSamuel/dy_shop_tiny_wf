import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  List,
  Select,
  Skeleton,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ApartmentOutlined,
  ApiOutlined,
  ArrowLeftOutlined,
  BranchesOutlined,
  DeploymentUnitOutlined,
  FunctionOutlined,
  PartitionOutlined,
  ReloadOutlined,
  RobotOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import { getOrchestrationGraph } from '@/services/orchestrationApi';
import type {
  OrchestrationCatalogSkill,
  OrchestrationCatalogTool,
  OrchestrationGraphNodeData,
  OrchestrationGraphPayload,
  OrchestrationNodeKind,
} from '@/types';

const { Title, Text, Paragraph } = Typography;

const kindConfig: Record<OrchestrationNodeKind, { label: string; color: string; icon: React.ReactNode }> = {
  workflow: { label: 'Workflow', color: 'blue', icon: <DeploymentUnitOutlined /> },
  agent: { label: 'Agent', color: 'purple', icon: <RobotOutlined /> },
  skill: { label: 'Skill', color: 'green', icon: <FunctionOutlined /> },
  tool: { label: 'Tool', color: 'gold', icon: <ToolOutlined /> },
  node: { label: 'Node', color: 'default', icon: <PartitionOutlined /> },
};

function OrchestrationNode({ data }: NodeProps) {
  const nodeData = data as unknown as OrchestrationGraphNodeData;
  const config = kindConfig[nodeData.kind] || kindConfig.node;
  const isInactive = nodeData.status && nodeData.status !== 'active';

  return (
    <div className={`orchestration-node orchestration-node--${nodeData.kind}`}>
      <Handle type="target" position={Position.Left} />
      <div className="orchestration-node-header">
        <span className="orchestration-node-icon">{config.icon}</span>
        <Tag color={config.color} style={{ margin: 0 }}>
          {config.label}
        </Tag>
        {nodeData.status ? (
          <Tag color={isInactive ? 'default' : 'success'} style={{ margin: 0 }}>
            {nodeData.status}
          </Tag>
        ) : null}
      </div>
      <div className="orchestration-node-title">{nodeData.label}</div>
      {nodeData.subtitle ? <div className="orchestration-node-subtitle">{nodeData.subtitle}</div> : null}
      {nodeData.nodeCount !== undefined ? (
        <div className="orchestration-node-meta">
          {nodeData.nodeCount} nodes · {nodeData.edgeCount} edges
        </div>
      ) : null}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { orchestrationNode: OrchestrationNode };

function listText(items?: string[]) {
  if (!items || items.length === 0) return '暂无';
  return items.join(' / ');
}

function buildSkillMap(payload: OrchestrationGraphPayload | null) {
  return new Map((payload?.skills || []).map((item) => [item.id, item]));
}

function buildToolMap(payload: OrchestrationGraphPayload | null) {
  return new Map((payload?.tools || []).map((item) => [item.id, item]));
}

interface DetailDrawerProps {
  payload: OrchestrationGraphPayload | null;
  node: OrchestrationGraphNodeData | null;
  open: boolean;
  onClose: () => void;
  onOpenWorkflow: (workflowId: string) => void;
}

function DetailDrawer({ payload, node, open, onClose, onOpenWorkflow }: DetailDrawerProps) {
  const skillMap = useMemo(() => buildSkillMap(payload), [payload]);
  const toolMap = useMemo(() => buildToolMap(payload), [payload]);

  if (!node) return null;

  const relatedSkills = (node.relatedSkills || [])
    .map((skillId) => skillMap.get(skillId))
    .filter(Boolean) as OrchestrationCatalogSkill[];
  const relatedTools = (node.relatedTools || [])
    .map((toolId) => toolMap.get(toolId))
    .filter(Boolean) as OrchestrationCatalogTool[];

  return (
    <Drawer
      title={
        <Space wrap>
          <Tag color={kindConfig[node.kind]?.color}>{kindConfig[node.kind]?.label || node.kind}</Tag>
          <span>{node.label}</span>
        </Space>
      }
      placement="right"
      width={540}
      open={open}
      onClose={onClose}
    >
      <Space direction="vertical" size={18} style={{ width: '100%' }}>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="节点 ID">{node.id}</Descriptions.Item>
          {node.nodeKey ? <Descriptions.Item label="Workflow 节点">{node.nodeKey}</Descriptions.Item> : null}
          <Descriptions.Item label="类型">{kindConfig[node.kind]?.label || node.kind}</Descriptions.Item>
          <Descriptions.Item label="状态">{node.status || '暂无'}</Descriptions.Item>
          <Descriptions.Item label="角色 / 类型">{node.role || node.roleType || node.subtitle || '暂无'}</Descriptions.Item>
          <Descriptions.Item label="来源文件">{node.filePath || '暂无'}</Descriptions.Item>
        </Descriptions>

        {node.description ? <Paragraph type="secondary">{node.description}</Paragraph> : null}

        {node.kind === 'workflow' ? (
          <Button type="primary" icon={<BranchesOutlined />} onClick={() => onOpenWorkflow(node.id)}>
            进入 Workflow 子图
          </Button>
        ) : null}

        <Card size="small" title="输入 / 输出">
          <Descriptions column={1} size="small">
            <Descriptions.Item label="主要输入">{listText(node.primaryInputs)}</Descriptions.Item>
            <Descriptions.Item label="主要输出">{listText(node.primaryOutputs)}</Descriptions.Item>
            <Descriptions.Item label="默认下一跳">{listText(node.defaultNext)}</Descriptions.Item>
          </Descriptions>
        </Card>

        <Card size="small" title="关联 Workflow">
          {node.relatedWorkflows?.length ? (
            <Space wrap>
              {node.relatedWorkflows.map((workflowId) => (
                <Button key={workflowId} size="small" onClick={() => onOpenWorkflow(workflowId)}>
                  {workflowId}
                </Button>
              ))}
            </Space>
          ) : (
            <Empty description="暂无关联 Workflow" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>

        <Card size="small" title="关联 Skill">
          {relatedSkills.length ? (
            <List
              size="small"
              dataSource={relatedSkills}
              renderItem={(skill) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<FunctionOutlined />}
                    title={
                      <Space>
                        <span>{skill.id}</span>
                        <Tag color="green">{skill.roleType}</Tag>
                      </Space>
                    }
                    description={`文件：${skill.filePath || '暂无'}；Tool：${listText(skill.tools)}`}
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无关联 Skill" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>

        <Card size="small" title="关联 Tool">
          {relatedTools.length ? (
            <List
              size="small"
              dataSource={relatedTools}
              renderItem={(tool) => (
                <List.Item>
                  <List.Item.Meta
                    avatar={<ApiOutlined />}
                    title={
                      <Space>
                        <span>{tool.id}</span>
                        <Tag color="gold">{tool.toolType}</Tag>
                      </Space>
                    }
                    description={`入口：${tool.backendEntry || tool.commandEntry || tool.invokeName || '暂无'}；实现：${tool.implementation || '暂无'}`}
                  />
                </List.Item>
              )}
            />
          ) : (
            <Empty description="暂无关联 Tool" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </Card>
      </Space>
    </Drawer>
  );
}

export default function OrchestrationGraph() {
  const { workflowId } = useParams();
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const [payload, setPayload] = useState<OrchestrationGraphPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<OrchestrationGraphNodeData | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const nextPayload = await getOrchestrationGraph();
      setPayload(nextPayload);
    } catch (error) {
      console.error('Failed to load orchestration graph', error);
      messageApi.error('编排图读取失败');
    } finally {
      setLoading(false);
    }
  }, [messageApi]);

  useEffect(() => {
    void loadGraph();
  }, [loadGraph]);

  const workflowGraph = workflowId ? payload?.workflowGraphs[workflowId] : null;
  const currentGraph = workflowGraph || payload?.rootGraph || { nodes: [], edges: [] };
  const nodes = currentGraph.nodes as Node<OrchestrationGraphNodeData>[];
  const edges = currentGraph.edges as Edge[];
  const isWorkflowView = Boolean(workflowId);

  const openWorkflow = useCallback(
    (targetWorkflowId: string) => {
      if (!payload?.workflowGraphs[targetWorkflowId]) {
        messageApi.warning('未找到该 Workflow 子图');
        return;
      }
      setDrawerOpen(false);
      navigate(`/project/orchestration/workflows/${targetWorkflowId}`);
    },
    [navigate, payload, messageApi],
  );

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node<OrchestrationGraphNodeData>) => {
      const data = node.data;
      if (data.kind === 'workflow') {
        openWorkflow(data.id);
        return;
      }
      setSelectedNode(data);
      setDrawerOpen(true);
    },
    [openWorkflow],
  );

  const selectedWorkflow = workflowId || '';

  return (
    <div className="page-shell orchestration-page">
      {contextHolder}
      <Card className="surface-card orchestration-hero">
        <div className="orchestration-hero-main">
          <Space direction="vertical" size={8}>
            <Space wrap>
              <Tag color="blue" icon={<ApartmentOutlined />}>
                .trae 编排资产
              </Tag>
              <Tag>事实源：{payload?.source.registry || '.trae/registry'}</Tag>
              <Tag>Workflow：{payload?.summary.workflowCount ?? '-'}</Tag>
              <Tag>Agent：{payload?.summary.activeAgentCount ?? '-'}/{payload?.summary.agentCount ?? '-'}</Tag>
              <Tag>Skill：{payload?.summary.skillCount ?? '-'}</Tag>
              <Tag>Tool：{payload?.summary.toolCount ?? '-'}</Tag>
            </Space>
            <Title level={3} style={{ margin: 0 }}>
              {isWorkflowView ? workflowGraph?.label || workflowId : '一级 Workflow 编排总图'}
            </Title>
            <Text type="secondary">
              {isWorkflowView
                ? workflowGraph?.description || '当前 Workflow 的直接子图、内部节点与边关系。点击 Workflow 节点可继续下钻。'
                : '从一级选流开始展示，点击 Workflow 后逐层进入子图；Web 只展示编排资产，不承载 Agent Runtime。'}
            </Text>
          </Space>
          <Space wrap>
            {isWorkflowView ? (
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/project/orchestration')}>
                返回总图
              </Button>
            ) : null}
            <Select
              allowClear
              showSearch
              placeholder="跳转 Workflow 子图"
              style={{ width: 280 }}
              value={selectedWorkflow || undefined}
              onChange={(value) => {
                if (value) openWorkflow(value);
                else navigate('/project/orchestration');
              }}
              options={(payload?.workflows || []).map((workflow) => ({
                label: `${workflow.label} (${workflow.id})`,
                value: workflow.id,
              }))}
              optionFilterProp="label"
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadGraph()} loading={loading}>
              刷新
            </Button>
          </Space>
        </div>
      </Card>

      {isWorkflowView && workflowId && !loading && !workflowGraph ? (
        <Alert
          type="warning"
          showIcon
          message="未找到 Workflow"
          description="当前 .trae/workflows 中没有对应 workflow_id，请返回总图重新选择。"
        />
      ) : null}

      <Card className="surface-card orchestration-graph-card" bodyStyle={{ padding: 0 }}>
        {loading ? (
          <div className="orchestration-loading">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        ) : nodes.length === 0 ? (
          <Empty className="orchestration-empty" description="暂无可展示的编排节点" />
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            onNodeClick={handleNodeClick}
            nodesDraggable
          >
            <Background color="#ffd6e7" gap={18} />
            <Controls />
            <MiniMap pannable zoomable nodeStrokeWidth={3} />
            <Panel position="top-left" className="orchestration-panel">
              <Space size={[6, 6]} wrap>
                <Tag color="blue">Workflow 点击下钻</Tag>
                <Tag color="purple">Agent 查看职责摘要</Tag>
                <Tag color="green">Skill / Tool 只在对应层展示</Tag>
              </Space>
            </Panel>
          </ReactFlow>
        )}
      </Card>

      {isWorkflowView && workflowGraph ? (
        <Card className="surface-card" title="Workflow 规则摘要">
          <Descriptions column={{ xs: 1, md: 2 }} size="small">
            <Descriptions.Item label="workflow_id">{workflowGraph.workflowId}</Descriptions.Item>
            <Descriptions.Item label="部长 / Controller">
              {workflowGraph.ministerRole || workflowGraph.workflowController || '暂无'}
            </Descriptions.Item>
            <Descriptions.Item label="父 Workflow">{workflowGraph.parentWorkflow || '无'}</Descriptions.Item>
            <Descriptions.Item label="子 Workflow">{listText(workflowGraph.childWorkflows)}</Descriptions.Item>
            <Descriptions.Item label="入口规则">{listText(workflowGraph.entryRules)}</Descriptions.Item>
            <Descriptions.Item label="成功标准">{listText(workflowGraph.successCriteria)}</Descriptions.Item>
          </Descriptions>
        </Card>
      ) : null}

      <DetailDrawer
        payload={payload}
        node={selectedNode}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onOpenWorkflow={openWorkflow}
      />
    </div>
  );
}
