import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MiniMap,
  Panel,
  ReactFlow,
  Handle,
  Position,
  ViewportPortal,
  type Edge,
  type EdgeProps,
  type EdgeTypes,
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

const { Title, Paragraph } = Typography;

const kindConfig: Record<OrchestrationNodeKind, { label: string; color: string; icon: React.ReactNode }> = {
  workflow: { label: 'Workflow', color: 'geekblue', icon: <DeploymentUnitOutlined /> },
  agent: { label: 'Agent', color: 'magenta', icon: <RobotOutlined /> },
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
      <Handle className="orchestration-handle--input" type="target" position={Position.Left} />
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
      <Handle className="orchestration-handle--output" type="source" position={Position.Right} />
    </div>
  );
}

const nodeTypes = { orchestrationNode: OrchestrationNode };
const ORCHESTRATION_NODE_WIDTH = 260;
const ORCHESTRATION_NODE_CENTER_Y = 56;

function getParallelNumber(data: Record<string, unknown> | undefined, key: string, fallback: number) {
  const value = data?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function getCubicPoint(
  start: number,
  controlA: number,
  controlB: number,
  end: number,
  progress = 0.5,
) {
  const inverse = 1 - progress;
  return (
    inverse ** 3 * start +
    3 * inverse ** 2 * progress * controlA +
    3 * inverse * progress ** 2 * controlB +
    progress ** 3 * end
  );
}

function toFlowElementId(id: string) {
  return id.replace(/[^a-zA-Z0-9_-]/g, '__');
}

function getBezierGeometry(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  edgeData?: Record<string, unknown>,
) {
  const parallelCount = getParallelNumber(edgeData, 'parallelCount', 1);
  const parallelOffset = getParallelNumber(edgeData, 'parallelOffset', 0);
  const isSelfLoop = Boolean(edgeData?.isSelfLoop);
  const offset = parallelCount > 1 ? parallelOffset * 0.45 : 0;
  const horizontalDistance = targetX - sourceX;
  const direction = horizontalDistance >= 0 ? 1 : -1;
  const curveDistance = Math.max(120, Math.abs(horizontalDistance) * 0.5);

  const controlA = isSelfLoop
    ? { x: sourceX + 180, y: sourceY - 120 - Math.abs(offset) }
    : { x: sourceX + direction * curveDistance, y: sourceY + offset };
  const controlB = isSelfLoop
    ? { x: targetX - 180, y: targetY - 120 - Math.abs(offset) }
    : { x: targetX - direction * curveDistance, y: targetY + offset };

  const path = `M ${sourceX},${sourceY} C ${controlA.x},${controlA.y} ${controlB.x},${controlB.y} ${targetX},${targetY}`;
  const labelX = getCubicPoint(sourceX, controlA.x, controlB.x, targetX);
  const labelY = getCubicPoint(sourceY, controlA.y, controlB.y, targetY);

  return { path, labelX, labelY };
}

function OrchestrationBezierEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  style,
  label,
  data,
}: EdgeProps) {
  const edgeData = data as Record<string, unknown> | undefined;
  const { path: edgePath, labelX, labelY } = getBezierGeometry(sourceX, sourceY, targetX, targetY, edgeData);

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="orchestration-edge-label"
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
}

const edgeTypes: EdgeTypes = { floatingBezier: OrchestrationBezierEdge };

function OrchestrationStaticEdges({
  nodes,
  edges,
}: {
  nodes: Node<OrchestrationGraphNodeData>[];
  edges: Edge[];
}) {
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  return (
    <ViewportPortal>
      <svg className="orchestration-static-edge-layer" aria-hidden="true">
        <defs>
          <marker
            id="orchestration-edge-arrow"
            markerWidth="12"
            markerHeight="12"
            refX="10"
            refY="6"
            orient="auto"
            markerUnits="strokeWidth"
          >
            <path d="M2,2 L10,6 L2,10 Z" />
          </marker>
        </defs>
        {edges.map((edge) => {
          const sourceNode = nodeById.get(edge.source);
          const targetNode = nodeById.get(edge.target);
          if (!sourceNode || !targetNode) return null;

          const edgeData = edge.data as Record<string, unknown> | undefined;
          const sourceX = sourceNode.position.x + ORCHESTRATION_NODE_WIDTH;
          const sourceY = sourceNode.position.y + ORCHESTRATION_NODE_CENTER_Y;
          const targetX = targetNode.position.x;
          const targetY = targetNode.position.y + ORCHESTRATION_NODE_CENTER_Y;
          const { path, labelX, labelY } = getBezierGeometry(sourceX, sourceY, targetX, targetY, edgeData);
          const labelText = edge.label ? String(edge.label) : '';

          return (
            <g key={edge.id} className="orchestration-static-edge">
              {labelText ? <title>{labelText}</title> : null}
              <path d={path} markerEnd="url(#orchestration-edge-arrow)" />
              {labelText ? (
                <foreignObject x={labelX - 130} y={labelY - 20} width={260} height={80}>
                  <div className="orchestration-edge-label orchestration-edge-label--svg">{labelText}</div>
                </foreignObject>
              ) : null}
            </g>
          );
        })}
      </svg>
    </ViewportPortal>
  );
}

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
  const rawNodes = currentGraph.nodes as Node<OrchestrationGraphNodeData>[];
  const flowNodeIdMap = useMemo(
    () => new Map(rawNodes.map((node) => [node.id, toFlowElementId(node.id)])),
    [rawNodes],
  );
  const nodes = useMemo(
    () =>
      rawNodes.map((node) => ({
        ...node,
        id: flowNodeIdMap.get(node.id) || toFlowElementId(node.id),
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      })),
    [flowNodeIdMap, rawNodes],
  );
  const edges = useMemo(
    () => {
      const mappedEdges = (currentGraph.edges as Edge[]).map((edge, index) => {
        return {
          id: `orchestration-edge-${index}`,
          source: flowNodeIdMap.get(edge.source) || toFlowElementId(edge.source),
          target: flowNodeIdMap.get(edge.target) || toFlowElementId(edge.target),
          label: edge.label,
          style: edge.style,
          data: edge.data,
          type: 'floatingBezier',
        };
      });
      return mappedEdges;
    },
    [currentGraph.edges, flowNodeIdMap],
  );
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
  const goToPreviousLayer = useCallback(() => {
    if (workflowGraph?.parentWorkflow && payload?.workflowGraphs[workflowGraph.parentWorkflow]) {
      navigate(`/project/orchestration/workflows/${workflowGraph.parentWorkflow}`);
      return;
    }
    navigate('/project/orchestration');
  }, [navigate, payload, workflowGraph]);

  return (
    <div className="page-shell orchestration-page">
      {contextHolder}
      <Card className="surface-card orchestration-hero">
        <div className="orchestration-hero-main">
          <Space className="orchestration-hero-summary" size={[10, 6]} wrap>
            <Title level={5} className="orchestration-hero-title">
              {isWorkflowView ? workflowGraph?.label || workflowId : '一级 Workflow 编排总图'}
            </Title>
            <Tag color="blue" icon={<ApartmentOutlined />}>
              .trae 编排资产
            </Tag>
            <Tag>事实源：{payload?.source.registry || '.trae/registry'}</Tag>
            <Tag>Workflow：{payload?.summary.workflowCount ?? '-'}</Tag>
            <Tag>Agent：{payload?.summary.activeAgentCount ?? '-'}/{payload?.summary.agentCount ?? '-'}</Tag>
            <Tag>Skill：{payload?.summary.skillCount ?? '-'}</Tag>
            <Tag>Tool：{payload?.summary.toolCount ?? '-'}</Tag>
          </Space>
          <Space wrap>
            {isWorkflowView ? (
              <Button icon={<ArrowLeftOutlined />} onClick={goToPreviousLayer}>
                返回上一层
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

      <Card
        className="surface-card orchestration-graph-card"
        bodyStyle={{ padding: 0 }}
      >
        {loading ? (
          <div className="orchestration-loading">
            <Skeleton active paragraph={{ rows: 8 }} />
          </div>
        ) : nodes.length === 0 ? (
          <Empty className="orchestration-empty" description="暂无可展示的编排节点" />
        ) : (
          <ReactFlow
            key={`${workflowId || 'root'}-${nodes.length}-${edges.length}`}
            nodes={nodes}
            edges={[]}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{ padding: 0.24 }}
            onNodeClick={handleNodeClick}
            nodesDraggable
            onlyRenderVisibleElements={false}
          >
            <OrchestrationStaticEdges nodes={nodes} edges={edges} />
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
            {isWorkflowView ? (
              <Panel position="top-right" className="orchestration-panel">
                <Button size="small" icon={<ArrowLeftOutlined />} onClick={goToPreviousLayer}>
                  返回上一层
                </Button>
              </Panel>
            ) : null}
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
