import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined } from '@ant-design/icons';
import { stickers } from '@/assets/stickerPack';
import type { RuntimeCapabilityCatalogItem, RuntimeExecutionRecord, RuntimeOverview } from '@/types';
import { getRuntimeLogs, getRuntimeOverview } from '@/services/runtimeApi';

const { Title, Text } = Typography;

const kindColorMap: Record<string, string> = {
  workflow: 'blue',
  agent: 'purple',
  skill: 'magenta',
  other: 'default',
};

const statusColorMap: Record<string, string> = {
  completed: 'green',
  running: 'gold',
  failed: 'red',
  pending: 'default',
  runtime_only: 'default',
  active: 'green',
  discovered: 'blue',
};

const formatTime = (value?: string | null) => {
  if (!value) return '暂无';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function ExecutionCenter() {
  const [messageApi, contextHolder] = message.useMessage();
  const [overview, setOverview] = useState<RuntimeOverview | null>(null);
  const [records, setRecords] = useState<RuntimeExecutionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [recordLoading, setRecordLoading] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [filters, setFilters] = useState({
    capability_kind: undefined as string | undefined,
    workflow_id: undefined as string | undefined,
    project_key: undefined as string | undefined,
    status: undefined as string | undefined,
    search: undefined as string | undefined,
  });

  const loadOverview = async () => {
    setLoading(true);
    try {
      const result = await getRuntimeOverview();
      setOverview(result);
      setRecords(result.recent_records);
    } catch (error) {
      console.error('Failed to load runtime overview', error);
      messageApi.error('执行记录中心读取失败');
    } finally {
      setLoading(false);
    }
  };

  const loadRecords = async (nextFilters = filters) => {
    setRecordLoading(true);
    try {
      const result = await getRuntimeLogs({
        ...nextFilters,
        limit: 120,
      });
      setRecords(result);
    } catch (error) {
      console.error('Failed to load runtime logs', error);
      messageApi.error('执行记录读取失败');
    } finally {
      setRecordLoading(false);
    }
  };

  useEffect(() => {
    void loadOverview();
  }, []);

  useEffect(() => {
    if (!overview) return;
    const hasFilter = Object.values(filters).some(Boolean);
    if (!hasFilter) {
      setRecords(overview.recent_records);
      return;
    }
    void loadRecords(filters);
  }, [filters, overview]);

  const failedCount = overview?.summary.status_counts.failed ?? 0;
  const runningCount = overview?.summary.status_counts.running ?? 0;

  const capabilityColumns: ColumnsType<RuntimeCapabilityCatalogItem> = useMemo(
    () => [
      {
        title: '能力',
        dataIndex: 'display_name',
        key: 'display_name',
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Space size={8} wrap>
              <Text strong>{record.display_name}</Text>
              <Tag color={kindColorMap[record.capability_kind] || 'default'}>{record.capability_kind}</Tag>
            </Space>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {record.capability_key}
            </Text>
            {record.file_path ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {record.file_path}
              </Text>
            ) : null}
          </Space>
        ),
      },
      {
        title: '状态',
        key: 'status',
        width: 130,
        render: (_, record) => (
          <Space direction="vertical" size={4}>
            <Tag color={statusColorMap[record.status] || 'default'}>{record.status}</Tag>
            {record.last_status ? <Tag color={statusColorMap[record.last_status] || 'default'}>{record.last_status}</Tag> : null}
          </Space>
        ),
      },
      {
        title: '作用域',
        key: 'workflow_scopes',
        render: (_, record) =>
          record.workflow_scopes?.length ? (
            <Space size={[6, 6]} wrap>
              {record.workflow_scopes.map((scope) => (
                <Tag key={scope}>{scope}</Tag>
              ))}
            </Space>
          ) : (
            <Text type="secondary">全局 / 未声明</Text>
          ),
      },
      {
        title: '记录',
        key: 'record_count',
        width: 180,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{record.record_count ?? 0}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              最近：{formatTime(record.last_run_at)}
            </Text>
          </Space>
        ),
      },
    ],
    []
  );

  return (
    <div className="page-shell">
      {contextHolder}
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <Card className="surface-card" loading={loading}>
          <Row gutter={[20, 20]} align="middle">
            <Col xs={24} lg={16}>
              <Space align="start" size={16}>
                <div className="project-card-icon" style={{ background: 'linear-gradient(135deg, #f5e6ff, #ffe6ef)', width: 80, height: 80 }}>
                  <img className="project-card-mascot" src={stickers.dashboard.auth} alt="执行记录中心" />
                </div>
                <div>
                  <Title level={3} style={{ margin: 0 }}>
                    执行记录中心
                  </Title>
                  <Text style={{ display: 'block', marginTop: 8, lineHeight: 1.75 }}>
                    统一查看 `agent / workflow / skill` 的登记目录和最近执行记录。新能力只要接入 `.trae` 目录或写入统一日志接口，这里就会自动出现。
                  </Text>
                  <Space size={[8, 8]} wrap style={{ marginTop: 14 }}>
                    <Tag color="blue">已登记 {overview?.summary.total_capabilities ?? 0}</Tag>
                    <Tag color={runningCount > 0 ? 'gold' : 'default'}>运行中 {runningCount}</Tag>
                    <Tag color={failedCount > 0 ? 'red' : 'green'}>失败 {failedCount}</Tag>
                    <Tag>24h 新记录 {overview?.summary.recent_records_24h ?? 0}</Tag>
                  </Space>
                </div>
              </Space>
            </Col>
            <Col xs={24} lg={8}>
              <Alert
                type={failedCount > 0 ? 'warning' : 'success'}
                showIcon
                message={failedCount > 0 ? '发现失败记录，建议先按状态过滤复看。' : '当前未发现失败记录。'}
                description="该页兼容 `workflow-log-publish`，也支持未来任意能力按统一协议写入。"
              />
              <div style={{ marginTop: 14, display: 'flex', justifyContent: 'flex-end' }}>
                <Button icon={<ReloadOutlined />} onClick={() => void loadOverview()}>
                  刷新
                </Button>
              </div>
            </Col>
          </Row>
        </Card>

        <Row gutter={[20, 20]}>
          <Col xs={12} md={6}>
            <Card className="surface-card" loading={loading}>
              <Statistic title="Workflows" value={overview?.summary.registered_workflows ?? 0} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="surface-card" loading={loading}>
              <Statistic title="Agents" value={overview?.summary.registered_agents ?? 0} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="surface-card" loading={loading}>
              <Statistic title="Skills" value={overview?.summary.registered_skills ?? 0} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card className="surface-card" loading={loading}>
              <Statistic title="累计记录" value={overview?.summary.total_records ?? 0} />
            </Card>
          </Col>
        </Row>

        <Card className="surface-card" loading={loading} title="筛选执行记录">
          <Space size={[12, 12]} wrap style={{ width: '100%' }}>
            <Input.Search
              allowClear
              placeholder="搜 workflow、agent、skill、摘要"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              onSearch={(value) => setFilters((current) => ({ ...current, search: value || undefined }))}
              style={{ width: 280 }}
            />
            <Select
              allowClear
              placeholder="能力类型"
              style={{ width: 140 }}
              value={filters.capability_kind}
              options={(overview?.filter_options.capability_kinds ?? []).map((item) => ({ label: item, value: item }))}
              onChange={(value) => setFilters((current) => ({ ...current, capability_kind: value }))}
            />
            <Select
              allowClear
              placeholder="工作流"
              style={{ width: 220 }}
              value={filters.workflow_id}
              options={(overview?.filter_options.workflow_ids ?? []).map((item) => ({ label: item, value: item }))}
              onChange={(value) => setFilters((current) => ({ ...current, workflow_id: value }))}
            />
            <Select
              allowClear
              placeholder="项目"
              style={{ width: 160 }}
              value={filters.project_key}
              options={(overview?.filter_options.project_keys ?? []).map((item) => ({ label: item, value: item }))}
              onChange={(value) => setFilters((current) => ({ ...current, project_key: value }))}
            />
            <Select
              allowClear
              placeholder="状态"
              style={{ width: 140 }}
              value={filters.status}
              options={(overview?.filter_options.status_values ?? []).map((item) => ({ label: item, value: item }))}
              onChange={(value) => setFilters((current) => ({ ...current, status: value }))}
            />
            <Button
              onClick={() => {
                setSearchInput('');
                setFilters({
                  capability_kind: undefined,
                  workflow_id: undefined,
                  project_key: undefined,
                  status: undefined,
                  search: undefined,
                });
              }}
            >
              清空
            </Button>
          </Space>
        </Card>

        <Row gutter={[20, 20]}>
          <Col xs={24} xl={14}>
            <Card className="surface-card" title="已登记能力目录" loading={loading}>
              <Table
                columns={capabilityColumns}
                dataSource={overview?.catalog ?? []}
                rowKey={(record) => `${record.capability_kind}:${record.capability_key}`}
                pagination={{ pageSize: 8 }}
                size="middle"
                locale={{ emptyText: '暂无能力目录' }}
              />
            </Card>
          </Col>
          <Col xs={24} xl={10}>
            <Card className="surface-card" title="最近执行记录" loading={loading || recordLoading}>
              {records.length ? (
                <List
                  dataSource={records}
                  renderItem={(item) => (
                    <List.Item>
                      <Card size="small" bordered={false} style={{ width: '100%', background: 'rgba(255,255,255,0.56)' }}>
                        <Space direction="vertical" size={8} style={{ width: '100%' }}>
                          <Space size={[8, 8]} wrap>
                            <Text strong>{item.title}</Text>
                            <Tag color={kindColorMap[item.capability_kind] || 'default'}>{item.capability_kind}</Tag>
                            <Tag color={statusColorMap[item.status] || 'default'}>{item.status}</Tag>
                            {item.phase ? <Tag>{item.phase}</Tag> : null}
                            {item.loop_round ? <Tag>第 {item.loop_round} 轮</Tag> : null}
                          </Space>
                          <Text>{item.summary || item.detail || '暂无摘要'}</Text>
                          {item.host_issue ? (
                            <Text type="secondary">宿主问题：{item.host_issue}</Text>
                          ) : null}
                          <Space size={[8, 8]} wrap>
                            <Text type="secondary">能力：{item.capability_key}</Text>
                            {item.workflow_id ? <Text type="secondary">工作流：{item.workflow_id}</Text> : null}
                            {item.source_key ? <Text type="secondary">来源：{item.source_key}</Text> : null}
                          </Space>
                          <Text type="secondary">时间：{formatTime(item.created_at)}</Text>
                        </Space>
                      </Card>
                    </List.Item>
                  )}
                />
              ) : (
                <Empty description="当前筛选条件下没有执行记录" />
              )}
            </Card>
          </Col>
        </Row>
      </Space>
    </div>
  );
}
