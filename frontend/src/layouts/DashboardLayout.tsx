import { Outlet, useNavigate } from 'react-router-dom';
import { Layout, Typography, Avatar, Dropdown } from 'antd';
import { UserOutlined, SettingOutlined, LogoutOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';

const { Header, Content } = Layout;

export default function DashboardLayout() {
  const navigate = useNavigate();

  const userMenuItems: MenuProps['items'] = [
    { key: 'settings', icon: <SettingOutlined />, label: '设置' },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录' },
  ];

  return (
    <Layout className="dashboard-shell" style={{ minHeight: '100vh' }}>
      <Header
        className="glass-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 32px',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          className="brand-group"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate('/')}
        >
          <div className="brand-mark">
            <span style={{ color: '#fff', fontWeight: 700, fontSize: 16 }}>P</span>
          </div>
          <div className="brand-copy">
            <Typography.Title className="brand-title" level={4} style={{ margin: 0, color: '#fff', fontWeight: 300 }}>
              Personal Studio
            </Typography.Title>
          </div>
        </div>
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Avatar
            icon={<UserOutlined />}
            style={{
              cursor: 'pointer',
              background: 'linear-gradient(135deg, rgba(255,255,255,0.24), rgba(40,223,212,0.28))',
              color: '#fff',
            }}
          />
        </Dropdown>
      </Header>
      <Content className="content-shell">
        <div className="page-shell">
          <Outlet />
        </div>
      </Content>
    </Layout>
  );
}
