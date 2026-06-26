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
          colorPrimary: '#ff9dc6',
          colorInfo: '#9ed8ff',
          colorSuccess: '#91d6bc',
          colorWarning: '#ffd88a',
          colorBgContainer: 'rgba(255, 255, 255, 0.86)',
          colorBorder: 'rgba(255, 183, 212, 0.32)',
          colorText: '#6b4c58',
          colorTextSecondary: '#9a7c89',
          boxShadowTertiary: '0 20px 60px rgba(234, 188, 208, 0.24)',
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
            darkItemSelectedBg: 'rgba(255, 182, 213, 0.34)',
            darkItemHoverBg: 'rgba(255, 255, 255, 0.44)',
            darkItemColor: '#8e6f7e',
            darkItemSelectedColor: '#6b4c58',
          },
          Card: {
            colorBgContainer: 'rgba(255, 255, 255, 0.84)',
          },
          Table: {
            headerBg: 'rgba(255, 244, 248, 0.92)',
            headerColor: '#7b5f6d',
            rowHoverBg: 'rgba(255, 246, 250, 0.92)',
            colorBgContainer: 'transparent',
            borderColor: 'rgba(255, 183, 212, 0.2)',
          },
          Button: {
            primaryShadow: '0 16px 32px rgba(255, 157, 198, 0.26)',
            defaultBg: 'rgba(255, 255, 255, 0.82)',
            defaultBorderColor: 'rgba(255, 183, 212, 0.24)',
          },
          Input: {
            activeBorderColor: '#ff9dc6',
            hoverBorderColor: '#ffc0db',
          },
          Select: {
            optionSelectedBg: 'rgba(255, 211, 229, 0.58)',
          },
          Tabs: {
            itemSelectedColor: '#6b4c58',
            itemActiveColor: '#6b4c58',
            inkBarColor: '#ff9dc6',
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
