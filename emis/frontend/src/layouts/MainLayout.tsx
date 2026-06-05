import React, { useState } from 'react';
import { Layout, Menu, Button, theme } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  DashboardOutlined,
  BankOutlined,
  SearchOutlined,
  LineChartOutlined,
  TeamOutlined,
  MessageOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import BrandLogo from '@/components/BrandLogo';

const { Header, Sider, Content } = Layout;

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const {
    token: { borderRadiusLG },
  } = theme.useToken();

  const menuItems: any[] = [
    {
      key: 'client',
      label: '前台业务',
      type: 'group',
      children: [
        {
          key: '/client/search',
          icon: <SearchOutlined />,
          label: '搜企搜标',
        },
        {
          key: '/client/analysis',
          icon: <LineChartOutlined />,
          label: '引用统计',
        },
        {
          key: '/client/members',
          icon: <TeamOutlined />,
          label: '会员中心',
        },
      ],
    },
    {
      key: 'admin',
      label: '后台管理',
      type: 'group',
      children: [
        {
          key: '/admin/dashboard',
          icon: <DashboardOutlined />,
          label: '控制台',
        },
        {
          key: '/admin/companies',
          icon: <BankOutlined />,
          label: '企业管理',
        },
        {
          key: '/admin/dict',
          icon: <SettingOutlined />,
          label: '字典配置',
        },
        {
          key: '/admin/sms-templates',
          icon: <MessageOutlined />,
          label: '短信模板',
        },
      ],
    },
  ];

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  return (
    <Layout style={{ minHeight: '100vh', background: '#f8fafc' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="light" style={{ borderRight: '1px solid #e2e8f0', background: '#ffffff' }}>
        <div style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          borderBottom: '1px solid #f1f5f9',
          background: '#ffffff'
        }}>
          <BrandLogo width={collapsed ? 36 : 48} height={collapsed ? 36 : 48} />
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: '#ffffff', borderRight: 0, padding: '12px 8px' }}
        />
      </Sider>
      <Layout style={{ background: '#f8fafc' }}>
        <Header style={{ 
          padding: '0 24px 0 0', 
          background: 'rgba(255, 255, 255, 0.75)', 
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          borderBottom: '1px solid rgba(226, 232, 240, 0.8)',
          position: 'sticky',
          top: 0,
          zIndex: 100
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: '16px', width: 64, height: 64 }}
          />
          <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout} danger>
            退出登录
          </Button>
        </Header>
        <Content
          style={{
            margin: '24px',
            padding: 24,
            minHeight: 280,
            background: '#ffffff',
            borderRadius: borderRadiusLG,
            boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05)',
            overflow: 'auto'
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
