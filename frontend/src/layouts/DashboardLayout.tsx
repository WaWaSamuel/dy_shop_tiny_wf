import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Dropdown, Button, Tooltip } from 'antd';
import type { MenuProps } from 'antd';
import StickerIcon from '@/components/common/StickerIcon';
import { stickers } from '@/assets/stickerPack';

const { Content } = Layout;

export default function DashboardLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const isHomePage = location.pathname === '/';
  const userMenuItems: MenuProps['items'] = [
    { key: 'settings', icon: <StickerIcon src={stickers.actions.filter} alt="设置" size="sm" />, label: '设置' },
    { type: 'divider' },
    { key: 'logout', icon: <StickerIcon src={stickers.brand.logout} alt="退出登录" size="sm" />, label: '退出登录' },
  ];

  return (
    <Layout className="dashboard-shell">
      <Content className="content-shell">
        <Outlet />
      </Content>
      {isHomePage ? (
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Button
            className="floating-corner-button floating-profile-button"
            type="text"
            shape="circle"
            icon={<StickerIcon src={stickers.brand.profile} alt="个人中心" size="xl" />}
          />
        </Dropdown>
      ) : (
        <Tooltip title="返回主页" placement="left">
          <Button
            className="floating-corner-button floating-home-button"
            type="text"
            shape="circle"
            icon={<StickerIcon src={stickers.nav.home} alt="返回主页" size="xl" className="floating-home-image" />}
            onClick={() => navigate('/')}
          />
        </Tooltip>
      )}
    </Layout>
  );
}
