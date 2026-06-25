import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { theme } from 'antd';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#28dfd4',
          colorInfo: '#28dfd4',
          colorSuccess: '#59f0cf',
          colorWarning: '#ffd76d',
          colorBgContainer: 'rgba(255, 255, 255, 0.14)',
          colorBorder: 'rgba(255, 255, 255, 0.12)',
          colorText: 'rgba(255, 255, 255, 0.92)',
          colorTextSecondary: 'rgba(255, 255, 255, 0.68)',
          boxShadowTertiary: '0 20px 60px rgba(32, 16, 68, 0.26)',
          borderRadius: 22,
          borderRadiusLG: 28,
          borderRadiusSM: 14,
          fontFamily:
            '"SF Pro Display", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
        components: {
          Layout: {
            bodyBg: 'transparent',
            siderBg: 'transparent',
            headerBg: 'transparent',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkSubMenuItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(40, 223, 212, 0.18)',
            darkItemHoverBg: 'rgba(255, 255, 255, 0.08)',
            darkItemColor: 'rgba(255, 255, 255, 0.72)',
            darkItemSelectedColor: '#ffffff',
          },
          Card: {
            colorBgContainer: 'rgba(255, 255, 255, 0.14)',
          },
          Table: {
            headerBg: 'rgba(255, 255, 255, 0.08)',
            headerColor: 'rgba(255, 255, 255, 0.88)',
            rowHoverBg: 'rgba(255, 255, 255, 0.06)',
            colorBgContainer: 'transparent',
            borderColor: 'rgba(255, 255, 255, 0.08)',
          },
          Button: {
            primaryShadow: '0 16px 32px rgba(40, 223, 212, 0.34)',
            defaultBg: 'rgba(255, 255, 255, 0.08)',
            defaultBorderColor: 'rgba(255, 255, 255, 0.12)',
          },
          Input: {
            activeBorderColor: '#28dfd4',
            hoverBorderColor: '#54efe4',
          },
          Select: {
            optionSelectedBg: 'rgba(40, 223, 212, 0.14)',
          },
          Tabs: {
            itemSelectedColor: '#ffffff',
            itemActiveColor: '#ffffff',
            inkBarColor: '#28dfd4',
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>
);
