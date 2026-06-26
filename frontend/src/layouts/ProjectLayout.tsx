import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Typography, Space, Button, Tooltip } from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Sider, Content } = Layout;

const menuItems = [
  { key: 'overview', icon: <StickerIcon src={stickers.menuOverview} alt="数据看板" size="sm" />, label: '数据看板' },
  { key: 'sourcing', icon: <StickerIcon src={stickers.menuSourcing} alt="选品中心" size="sm" />, label: '选品中心' },
  { key: 'products', icon: <StickerIcon src={stickers.menuSupply} alt="货源管理" size="sm" />, label: '货源管理' },
  { key: 'creative-studio', icon: <StickerIcon src={stickers.menuCreative} alt="广告资产" size="sm" />, label: '广告资产 / 资产工作台' },
  { key: 'products', icon: <StickerIcon src={stickers.menuProduct} alt="商品管理" size="sm" />, label: '商品管理' },
  { key: 'orders', icon: <StickerIcon src={stickers.menuOrders} alt="订单与物流" size="sm" />, label: '订单与物流' },
  { key: 'after-sales', icon: <StickerIcon src={stickers.menuService} alt="售后服务" size="sm" />, label: '售后服务' },
  { key: 'finance', icon: <StickerIcon src={stickers.menuFinance} alt="财务中心" size="sm" />, label: '财务中心' },
  { key: 'analytics', icon: <StickerIcon src={stickers.menuAnalytics} alt="数据分析" size="sm" />, label: '数据分析' },
  { key: 'flow/default', icon: <StickerIcon src={stickers.menuFlow} alt="商品全链路" size="sm" />, label: '商品全链路' },
  { key: 'settings', icon: <StickerIcon src={stickers.menuSettings} alt="设置" size="sm" />, label: '设置' },
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
            borderBottom: '1px solid rgba(255, 188, 216, 0.18)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {!collapsed && (
            <Space>
              <div className="brand-mark" style={{ width: 30, height: 30, borderRadius: 10 }}>
                  <img className="brand-image" src={stickers.menuSupply} alt="电商工作台" />
              </div>
              <div>
                <Typography.Text strong style={{ color: 'var(--text-main)' }}>电商工作台</Typography.Text>
              </div>
            </Space>
          )}
          <Button
            type="text"
            icon={<StickerIcon src={collapsed ? stickers.toggleOpen : stickers.toggleClose} alt="展开侧边栏" size="sm" />}
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
            <img className="project-sider-sticker project-sider-sticker--a" src={stickers.siderStickerA} alt="" />
            <img className="project-sider-sticker project-sider-sticker--b" src={stickers.siderStickerB} alt="" />
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
          icon={<StickerIcon src={stickers.homeButton} alt="返回主页" size="xl" className="floating-home-image" />}
          onClick={() => navigate('/')}
        />
      </Tooltip>
    </Layout>
  );
}
