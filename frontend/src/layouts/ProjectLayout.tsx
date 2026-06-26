import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Button, Tooltip } from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Sider, Content } = Layout;

const menuItems = [
  { key: 'overview', icon: <StickerIcon src={stickers.nav.overview} alt="数据看板" size="sm" />, label: '数据看板' },
  { key: 'sourcing', icon: <StickerIcon src={stickers.nav.sourcing} alt="1688 选品" size="sm" />, label: '1688 选品' },
  { key: 'products', icon: <StickerIcon src={stickers.nav.catalog} alt="抖掌柜货盘" size="sm" />, label: '抖掌柜货盘' },
  { key: 'creative-studio', icon: <StickerIcon src={stickers.nav.creative} alt="素材工坊" size="sm" />, label: '素材工坊' },
  { key: 'flow/default', icon: <StickerIcon src={stickers.nav.flow} alt="流程看板" size="sm" />, label: '流程看板' },
];

export default function ProjectLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const rawPath = location.pathname.split('/project/ecommerce/')[1] || 'overview';
  const currentPath = rawPath.startsWith('flow/') ? 'flow/default' : rawPath;

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
            borderBottom: '1px solid rgba(255, 188, 216, 0.18)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {!collapsed && (
            <Space>
              <div className="brand-mark" style={{ width: 30, height: 30, borderRadius: 10 }}>
                  <img className="brand-image" src={stickers.brand.mark} alt="电商工作台" />
              </div>
              <div>
                <Typography.Text strong style={{ color: 'var(--text-main)' }}>电商工作台</Typography.Text>
              </div>
            </Space>
          )}
          <Button
            type="text"
            icon={<StickerIcon src={collapsed ? stickers.nav.toggleOpen : stickers.nav.toggleClose} alt="展开侧边栏" size="sm" />}
            onClick={() => setCollapsed(!collapsed)}
            size="small"
            style={{ color: 'var(--text-main)' }}
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
        {!collapsed && (
          <div className="project-sider-sticker-cluster" aria-hidden="true">
            <img className="project-sider-sticker project-sider-sticker--a" src={stickers.decor.sidebarA} alt="" />
            <img className="project-sider-sticker project-sider-sticker--b" src={stickers.decor.sidebarB} alt="" />
            <div className="project-sider-note">
              抖掌柜负责物流跟踪与抖店上架，
              <br />
              这里负责货盘读取与经营协同。
            </div>
          </div>
        )}
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 98 : 258, transition: 'margin-left 0.2s' }}>
        <Content className="content-shell project-content-shell" style={{ minHeight: '100vh' }}>
          <div className="project-workbench-surface">
            <div className="page-shell page-shell--workbench">
              <Outlet />
            </div>
          </div>
        </Content>
      </Layout>
      <Tooltip title="返回主页" placement="left">
        <Button
          className="floating-corner-button floating-home-button"
          type="text"
          shape="circle"
          icon={<StickerIcon src={stickers.nav.home} alt="返回主页" size="xl" className="floating-home-image" />}
          onClick={() => navigate('/')}
        />
      </Tooltip>
    </Layout>
  );
}
