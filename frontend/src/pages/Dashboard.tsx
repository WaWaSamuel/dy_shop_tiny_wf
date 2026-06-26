import { useNavigate } from 'react-router-dom';
import { Card, Row, Col, Typography, Tag, Space, Badge } from 'antd';
import { stickers } from '@/assets/stickerPack';

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
}

const projects: ProjectCard[] = [
  {
    key: 'ecommerce',
    title: '跨境电商工作台',
    description: '全链路跨境电商管理平台，涵盖选品、货源、广告素材生成、商品管理、订单物流等模块',
    icon: <img className="project-card-mascot" src={stickers.dashboardStickerEcommerce} alt="跨境电商工作台" />,
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
    icon: <img className="project-card-mascot" src={stickers.dashboardStickerStocks} alt="量化投资系统" />,
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
    icon: <img className="project-card-mascot" src={stickers.dashboardStickerNews} alt="资讯聚合引擎" />,
    color: '#ffe0a3',
    gradient: 'linear-gradient(135deg, #fff1c6, #ffe3a5)',
    status: 'planned',
    route: '/project/news',
    tags: ['RSS', 'AI摘要', '情绪分析'],
  },
  {
    key: 'auth',
    title: '统一认证中心',
    description: '多项目统一身份认证与权限管理系统，支持 OAuth2、RBAC、多租户',
    icon: <img className="project-card-mascot" src={stickers.dashboardStickerAuth} alt="统一认证中心" />,
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

export default function Dashboard() {
  const navigate = useNavigate();

  return (
    <div className="page-shell dashboard-home-scene">
      <div className="dashboard-home-stage" aria-hidden="true">
        <div className="dashboard-home-wall" />
        <div className="dashboard-home-glow dashboard-home-glow--left" />
        <div className="dashboard-home-glow dashboard-home-glow--right" />
      </div>
      <div className="dashboard-home-content">
        <Row gutter={[24, 24]} className="dashboard-entry-grid">
          {projects.map((project, index) => (
            <Col
              xs={24}
              sm={12}
              lg={6}
              key={project.key}
              className={index === 0 ? 'dashboard-entry-col dashboard-entry-col--primary' : 'dashboard-entry-col'}
            >
              <Badge.Ribbon
                text={statusConfig[project.status].label}
                color={statusConfig[project.status].color}
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
              </Badge.Ribbon>
            </Col>
          ))}
        </Row>
      </div>
    </div>
  );
}
