import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Card,
  Col,
  Row,
  Space,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ReloadOutlined,
} from '@ant-design/icons';
import { stickers } from '@/assets/stickerPack';
import { getSessionSources, syncSessionSourceViaBridge } from '@/services/sessionSourceApi';
import type { SessionSource } from '@/types';

const { Title, Text } = Typography;

interface ProjectCard {
  key: string;
  title: string;
  description: string;
  summary: string;
  icon: React.ReactNode;
  color: string;
  gradient: string;
  status: 'active' | 'developing' | 'planned' | 'paused';
  route: string;
  tags: string[];
  dependencies?: string[];
}

const projects: ProjectCard[] = [
  {
    key: 'ecommerce',
    title: '电商结果展示台',
    description: '聚合 agent 已完成的货盘结果、候选推荐、素材结果和流程轨迹，优先展示当前最值得复看的工作对象',
    summary: '优先入口',
    icon: <img className="project-card-mascot" src={stickers.dashboard.ecommerce} alt="跨境电商工作台" />,
    color: '#ffb6d5',
    gradient: 'linear-gradient(135deg, #ffd7e7, #ffe7c4)',
    status: 'active',
    route: '/project/ecommerce',
    tags: ['结果快照', '候选推荐', '流程轨迹'],
  },
  {
    key: 'runtime',
    title: '执行记录中心',
    description: '统一查看 agent、workflow、skill 的登记目录与执行记录，对后续新增能力自动生效',
    summary: '新增入口',
    icon: <img className="project-card-mascot" src={stickers.dashboard.auth} alt="执行记录中心" />,
    color: '#d8d4ff',
    gradient: 'linear-gradient(135deg, #efe8ff, #ffdfe9)',
    status: 'active',
    route: '/project/runtime',
    tags: ['Agent 记录', 'Workflow 轨迹', 'Skill 日志'],
  },
  {
    key: 'orchestration',
    title: '编排可视化图谱',
    description: '用 ReactFlow 查看 .trae 下 agent、workflow、skill、tool 的编排关系，支持进入 Workflow 子图',
    summary: '编排入口',
    icon: <img className="project-card-mascot" src={stickers.dashboard.auth} alt="编排可视化图谱" />,
    color: '#c8e7ff',
    gradient: 'linear-gradient(135deg, #dff2ff, #ffe2ef)',
    status: 'active',
    route: '/project/orchestration',
    tags: ['ReactFlow', '嵌套子图', '.trae 资产'],
  },
  {
    key: 'stocks',
    title: '量化结果看板',
    description: '沉淀策略信号、仓位变化和风险结果，作为后续量化项目的统一结果入口',
    summary: '后续扩展',
    icon: <img className="project-card-mascot" src={stickers.dashboard.stocks} alt="量化投资系统" />,
    color: '#9ed8ff',
    gradient: 'linear-gradient(135deg, #d8efff, #cfe7ff)',
    status: 'developing',
    route: '/project/stocks',
    tags: ['策略结果', '持仓轨迹', '风险提醒'],
  },
  {
    key: 'news',
    title: '资讯结果看板',
    description: '汇总资讯抓取结果、热点主题和摘要卡片，让每天的资讯输出按结果顺序展开',
    summary: '今日可用',
    icon: <img className="project-card-mascot" src={stickers.dashboard.news} alt="资讯聚合引擎" />,
    color: '#ffe0a3',
    gradient: 'linear-gradient(135deg, #fff1c6, #ffe3a5)',
    status: 'active',
    route: '/project/news',
    tags: ['资讯摘要', '热点提炼', '飞书推送'],
    dependencies: ['weread'],
  },
  {
    key: 'auth',
    title: '宿主与登录态中心',
    description: '集中展示网页登录态、Bridge 状态和需要人工恢复的外部依赖，方便守门和回流',
    summary: '宿主守门',
    icon: <img className="project-card-mascot" src={stickers.dashboard.auth} alt="统一认证中心" />,
    color: '#d8d4ff',
    gradient: 'linear-gradient(135deg, #ece6ff, #dde7ff)',
    status: 'active',
    route: '/project/auth',
    tags: ['OAuth2', 'RBAC', 'SSO'],
  },
];

const statusConfig: Record<string, { label: string; color: string }> = {
  active: { label: '运行中', color: '#ffbdd9' },
  developing: { label: '开发中', color: '#b8dfff' },
  planned: { label: '规划中', color: '#ffe3a1' },
  paused: { label: '已暂停', color: '#d8d3ee' },
};

const formatTime = (value?: string | null) => {
  if (!value) {
    return '尚无记录';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();
  const [sessionSources, setSessionSources] = useState<SessionSource[]>([]);
  const [sessionLoading, setSessionLoading] = useState(true);

  const loadSessionSources = async (refresh = false) => {
    setSessionLoading(true);
    try {
      const nextSources = await getSessionSources(refresh);
      setSessionSources(nextSources);
    } catch (error) {
      console.error('Failed to load session sources', error);
      messageApi.error('外部站点状态读取失败');
    } finally {
      setSessionLoading(false);
    }
  };

  useEffect(() => {
    void loadSessionSources(true);
  }, []);

  useEffect(() => {
    const refreshOnFocus = () => {
      if (document.visibilityState !== 'hidden') {
        void handleRefreshSessionSources();
      }
    };

    window.addEventListener('focus', refreshOnFocus);
    document.addEventListener('visibilitychange', refreshOnFocus);
    return () => {
      window.removeEventListener('focus', refreshOnFocus);
      document.removeEventListener('visibilitychange', refreshOnFocus);
    };
  }, []);

  const expiredSources = sessionSources.filter((item) => item.status === 'expired');
  const unhealthySourceIds = new Set(expiredSources.map((item) => item.id));
  const orderedSessionSources = useMemo(
    () => [...sessionSources].sort((left, right) => left.name.localeCompare(right.name, 'zh-CN')),
    [sessionSources],
  );
  const healthySourceCount = sessionSources.filter((item) => item.healthy).length;
  const unhealthySourceCount = sessionSources.length - healthySourceCount;
  const heroStatusText = unhealthySourceCount > 0 ? '宿主守门中' : '结果读取正常';

  const renderSessionTooltip = (source: SessionSource) => (
    <div className="dashboard-session-tooltip">
      <div className="dashboard-session-tooltip-title">{source.name}</div>
      <div>{source.healthy ? '状态正常' : '需要重新登录'}</div>
      <div>{source.message}</div>
      <div>最近检查：{formatTime(source.lastCheckedAt)}</div>
      <div>最近成功：{formatTime(source.lastSuccessAt)}</div>
      {source.probeDetail.displayName ? <div>当前账号：{source.probeDetail.displayName}</div> : null}
      {source.lastError ? <div>最近错误：{source.lastError}</div> : null}
      <div>点击可打开网页并手动登录。</div>
    </div>
  );

  const handleRefreshSessionSources = async () => {
    setSessionLoading(true);
    try {
      const staleSources = sessionSources.filter((item) => !item.healthy);
      if (staleSources.length > 0) {
        const results = await Promise.allSettled(staleSources.map((item) => syncSessionSourceViaBridge(item.id)));
        const successCount = results.filter((item) => item.status === 'fulfilled').length;
        const failedCount = results.length - successCount;
        if (successCount > 0) {
          messageApi.success(`已同步 ${successCount} 个网页登录态`);
        }
        if (failedCount > 0) {
          messageApi.warning(`${failedCount} 个网页登录态同步失败，已回退为普通重检`);
        }
      }

      const nextSources = await getSessionSources(true);
      setSessionSources(nextSources);
    } catch (error) {
      console.error('Failed to refresh session sources with bridge sync', error);
      messageApi.error('网页登录态刷新失败');
      try {
        const nextSources = await getSessionSources(true);
        setSessionSources(nextSources);
      } catch (fallbackError) {
        console.error('Fallback refresh failed', fallbackError);
      }
    } finally {
      setSessionLoading(false);
    }
  };

  return (
    <div className="page-shell dashboard-home-scene">
      {contextHolder}
      <div className="dashboard-home-stage" aria-hidden="true">
        <div className="dashboard-home-wall" />
        <div className="dashboard-home-glow dashboard-home-glow--left" />
        <div className="dashboard-home-glow dashboard-home-glow--right" />
      </div>
      <div className="dashboard-home-content">
        <div className="dashboard-home-stack">
          <Card className="surface-card" style={{ marginBottom: 24, borderRadius: 28, background: 'rgba(255,255,255,0.72)' }}>
            <Row gutter={[24, 24]} align="middle">
              <Col xs={24} lg={15}>
                <Space align="start" size={16}>
                  <div className="project-card-icon" style={{ background: 'linear-gradient(135deg, #ffe4ef, #fff1c9)', width: 84, height: 84 }}>
                    <img className="project-card-mascot" src={stickers.dashboard.ecommerce} alt="结果展示台" />
                  </div>
                  <div>
                    <Title level={3} style={{ margin: 0 }}>个人结果展示台</Title>
                    <Text style={{ display: 'block', marginTop: 10, fontSize: 14, lineHeight: 1.75 }}>
                      agents 在外部完成工作，这里只负责把工作结果、候选建议、素材结果、资讯摘要和宿主状态整理成一眼能读懂的看板。
                    </Text>
                    <Space size={[8, 8]} wrap style={{ marginTop: 14 }}>
                      <Tag color={unhealthySourceCount > 0 ? 'gold' : 'green'}>{heroStatusText}</Tag>
                      <Tag color="blue">结果入口 {projects.filter((item) => item.status === 'active').length} 个</Tag>
                      <Tag>正常登录态 {healthySourceCount}</Tag>
                      <Tag color={unhealthySourceCount > 0 ? 'red' : 'default'}>待恢复 {unhealthySourceCount}</Tag>
                    </Space>
                  </div>
                </Space>
              </Col>
              <Col xs={24} lg={9}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
                  <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.6)', borderRadius: 20 }}>
                    <Text type="secondary">主入口</Text>
                    <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>电商结果展示台</div>
                  </Card>
                  <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.6)', borderRadius: 20 }}>
                    <Text type="secondary">今日状态</Text>
                    <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>{heroStatusText}</div>
                  </Card>
                  <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.6)', borderRadius: 20 }}>
                    <Text type="secondary">资讯链路</Text>
                    <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>{projects.find((item) => item.key === 'news')?.status === 'active' ? '已挂载' : '待补充'}</div>
                  </Card>
                  <Card size="small" bordered={false} style={{ background: 'rgba(255,255,255,0.6)', borderRadius: 20 }}>
                    <Text type="secondary">宿主守门</Text>
                    <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4 }}>{sessionLoading ? '检查中' : '可查看'}</div>
                  </Card>
                </div>
              </Col>
            </Row>
          </Card>

          <Row gutter={[24, 24]} className="dashboard-entry-grid">
            {projects.map((project, index) => (
              <Col
                xs={24}
                sm={12}
                lg={6}
                key={project.key}
                className={index === 0 ? 'dashboard-entry-col dashboard-entry-col--primary' : 'dashboard-entry-col'}
              >
                <Badge.Ribbon text={statusConfig[project.status].label} color={statusConfig[project.status].color}>
                  <Badge
                    count={project.dependencies?.some((item) => unhealthySourceIds.has(item)) ? '!' : 0}
                    color="#ff6b81"
                    offset={[-2, 10]}
                  >
                    <Card
                      className={index === 0 ? 'dashboard-grid-card dashboard-grid-card--primary' : 'dashboard-grid-card'}
                      hoverable
                      style={{
                        height: '100%',
                        overflow: 'hidden',
                      }}
                      onClick={() => navigate(project.route)}
                    >
                      <div className="project-card-icon" style={{ background: project.gradient }}>
                        {project.icon}
                      </div>
                      <Title level={5} className="project-card-title">
                        {project.title}
                      </Title>
                      <Tag color={index === 0 ? 'magenta' : 'default'} style={{ borderRadius: 999, marginBottom: 10 }}>
                        {project.summary}
                      </Tag>
                      <Text className="project-card-desc" style={{ fontSize: 13, display: 'block', marginBottom: 16 }}>
                        {project.description}
                      </Text>
                      <Space className="project-card-tags" size={[4, 4]} wrap>
                        {project.tags.map((tag) => (
                          <Tag key={tag} style={{ borderRadius: 4 }}>
                            {tag}
                          </Tag>
                        ))}
                      </Space>
                    </Card>
                  </Badge>
                </Badge.Ribbon>
              </Col>
            ))}
          </Row>

          <div className="dashboard-session-strip">
            <div className="dashboard-session-strip-inner">
              <Text type="secondary" style={{ marginRight: 8 }}>
                宿主登录态
              </Text>
              <Space size={10} wrap className="dashboard-session-strip-items">
                {orderedSessionSources.map((source) => (
                  <Tooltip key={source.id} title={renderSessionTooltip(source)} placement="top">
                    <button
                      type="button"
                      className="dashboard-session-pill"
                      onClick={() => window.open(source.loginUrl || source.homepageUrl, '_blank', 'noopener,noreferrer')}
                    >
                      <span
                        className={`dashboard-session-pill-light ${source.healthy ? 'is-healthy' : 'is-danger'}`}
                      />
                      <span className="dashboard-session-pill-name">{source.name}</span>
                    </button>
                  </Tooltip>
                ))}
              </Space>
              <button
                type="button"
                className="dashboard-session-refresh"
                onClick={() => void handleRefreshSessionSources()}
                disabled={sessionLoading}
                aria-label="刷新网页登录监控"
              >
                <ReloadOutlined spin={sessionLoading} />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
