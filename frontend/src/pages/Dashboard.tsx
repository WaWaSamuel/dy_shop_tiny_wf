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
    title: '跨境电商工作台',
    description: '全链路跨境电商管理平台，涵盖选品、货源、广告素材生成、商品管理、订单物流等模块',
    icon: <img className="project-card-mascot" src={stickers.dashboard.ecommerce} alt="跨境电商工作台" />,
    color: '#ffb6d5',
    gradient: 'linear-gradient(135deg, #ffd7e7, #ffe7c4)',
    status: 'active',
    route: '/project/ecommerce',
    tags: ['TikTok Shop', 'Temu', '独立站'],
  },
  {
    key: 'stocks',
    title: '量化投资系统',
    description: '股票与加密货币量化交易系统，支持策略回测、实盘信号、持仓分析、风险控制',
    icon: <img className="project-card-mascot" src={stickers.dashboard.stocks} alt="量化投资系统" />,
    color: '#9ed8ff',
    gradient: 'linear-gradient(135deg, #d8efff, #cfe7ff)',
    status: 'developing',
    route: '/project/stocks',
    tags: ['A股', '美股', '加密货币'],
  },
  {
    key: 'news',
    title: '资讯聚合引擎',
    description: '多源资讯抓取与聚合分析平台，AI 摘要、热点追踪、情绪分析、定制推送',
    icon: <img className="project-card-mascot" src={stickers.dashboard.news} alt="资讯聚合引擎" />,
    color: '#ffe0a3',
    gradient: 'linear-gradient(135deg, #fff1c6, #ffe3a5)',
    status: 'planned',
    route: '/project/news',
    tags: ['RSS', 'AI摘要', '情绪分析'],
    dependencies: ['weread'],
  },
  {
    key: 'auth',
    title: '统一认证中心',
    description: '多项目统一身份认证与权限管理系统，支持 OAuth2、RBAC、多租户',
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
