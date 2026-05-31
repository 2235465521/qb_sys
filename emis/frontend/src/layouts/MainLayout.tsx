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
    token: { colorBgContainer, borderRadiusLG },
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
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="light" style={{ boxShadow: '2px 0 8px 0 rgba(29,33,41,.05)' }}>
        <div style={{ 
          height: 64, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center', 
          gap: 8,
          borderBottom: '1px solid #f0f0f0',
          background: '#fff'
        }}>
          <BrandLogo width={collapsed ? 28 : 32} height={collapsed ? 28 : 32} />
          {!collapsed && (
            <span style={{ 
              fontWeight: 800, 
              fontSize: 16, 
              color: '#141414', 
              letterSpacing: '0.5px',
              fontFamily: '"Outfit", sans-serif' 
            }}>
              ESIM SYSTEM
            </span>
          )}
        </div>
        <Menu
          theme="light"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: 24 }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: '16px', width: 64, height: 64 }}
          />
          <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout}>
            退出登录
          </Button>
        </Header>
        <Content
          style={{
            margin: '24px 16px',
            padding: 24,
            minHeight: 280,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
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
