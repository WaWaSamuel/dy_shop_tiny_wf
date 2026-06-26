import { Outlet } from 'react-router-dom';
import { Layout, Dropdown, Button } from 'antd';
import type { MenuProps } from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Content } = Layout;

export default function DashboardLayout() {
  const userMenuItems: MenuProps['items'] = [
    { key: 'settings', icon: <StickerIcon src={stickers.actions.filter} alt="设置" size="sm" />, label: '设置' },
    { type: 'divider' },
    { key: 'logout', icon: <StickerIcon src={stickers.brand.logout} alt="退出登录" size="sm" />, label: '退出登录' },
  ];

  return (
    <Layout className="dashboard-shell" style={{ minHeight: '100vh' }}>
      <Content className="content-shell">
        <div className="page-shell">
          <Outlet />
        </div>
      </Content>
      <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
        <Button
          className="floating-corner-button floating-profile-button"
          type="text"
          shape="circle"
          icon={<StickerIcon src={stickers.brand.profile} alt="个人中心" size="xl" />}
        />
      </Dropdown>
    </Layout>
  );
}
