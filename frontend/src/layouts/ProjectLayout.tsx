import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Button, Tooltip } from 'antd';
import {
  DashboardOutlined,
  SearchOutlined,
  ShopOutlined,
  PictureOutlined,
  AppstoreOutlined,
  TruckOutlined,
  CustomerServiceOutlined,
  DollarOutlined,
  BarChartOutlined,
  NodeIndexOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  HomeOutlined,
} from '@ant-design/icons';

const { Sider, Content } = Layout;

const menuItems = [
  { key: 'overview', icon: <DashboardOutlined />, label: '数据看板' },
  { key: 'sourcing', icon: <SearchOutlined />, label: '选品中心' },
  { key: 'products', icon: <ShopOutlined />, label: '货源管理' },
  { key: 'creative-studio', icon: <PictureOutlined />, label: '广告资产 / 资产工作台' },
  { key: 'products', icon: <AppstoreOutlined />, label: '商品管理' },
  { key: 'orders', icon: <TruckOutlined />, label: '订单与物流' },
  { key: 'after-sales', icon: <CustomerServiceOutlined />, label: '售后服务' },
  { key: 'finance', icon: <DollarOutlined />, label: '财务中心' },
  { key: 'analytics', icon: <BarChartOutlined />, label: '数据分析' },
  { key: 'flow/default', icon: <NodeIndexOutlined />, label: '商品全链路' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置' },
];

export default function ProjectLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const currentPath = location.pathname.split('/project/ecommerce/')[1] || 'overview';

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(`/project/ecommerce/${key}`);
  };

  return (
    <Layout className="project-shell" style={{ minHeight: '100vh' }}>
      <Sider
        className="project-sider"
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={240}
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: collapsed ? '16px 8px' : '16px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {!collapsed && (
            <Space>
              <div className="brand-mark" style={{ width: 30, height: 30, borderRadius: 10 }}>
                <ShopOutlined style={{ color: '#fff', fontSize: 14 }} />
              </div>
              <div>
                <Typography.Text strong style={{ color: '#fff' }}>电商工作台</Typography.Text>
              </div>
            </Space>
          )}
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            size="small"
            style={{ color: '#fff' }}
          />
        </div>
        <Menu
          className="project-menu"
          theme="dark"
          mode="inline"
          selectedKeys={[currentPath]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ border: 'none', marginTop: 8, background: 'transparent' }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 98 : 258, transition: 'margin-left 0.2s' }}>
        <Content className="content-shell project-content-shell" style={{ minHeight: '100vh' }}>
          <div className="page-shell">
            <Outlet />
          </div>
        </Content>
      </Layout>
      <Tooltip title="返回主页" placement="left">
        <Button
          className="floating-home-button"
          type="text"
          shape="circle"
          icon={<HomeOutlined />}
          onClick={() => navigate('/')}
        />
      </Tooltip>
    </Layout>
  );
}
