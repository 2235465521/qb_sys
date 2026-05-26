import React, { useState } from 'react';
import { Layout, Menu, Button, theme, Space, Avatar } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  LineChartOutlined,
  TeamOutlined,
  LogoutOutlined,
  UserOutlined,
  FileTextOutlined,
  RadarChartOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useQueryClient } from '@tanstack/react-query';

const { Header, Sider, Content } = Layout;

const ClientLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const menuItems = [
    {
      key: '/client/search',
      icon: <SearchOutlined />,
      label: '查询企业',
    },
    {
      key: '/client/standards',
      icon: <FileTextOutlined />,
      label: '搜索企标',
    },
    {
      key: '/client/analysis',
      icon: <LineChartOutlined />,
      label: '引用记录',
    },
    {
      key: '/client/trends',
      icon: <RadarChartOutlined />,
      label: '研发风向标',
    },
    {
      key: '/client/members',
      icon: <TeamOutlined />,
      label: '会员中心',
    },
  ];

  const handleLogout = () => {
    localStorage.clear();
    queryClient.clear();
    navigate('/login');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: collapsed ? 12 : 20, color: '#1677ff' }}>
          {collapsed ? 'EMIS' : '应用搜索'}
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
        <Header style={{ padding: '0 24px', background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #f0f0f0' }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: '16px', width: 64, height: 64 }}
          />
          <Space size="large">
            {isAdmin && (
              <Button 
                type="primary" 
                ghost 
                onClick={() => navigate('/admin')}
                style={{ borderRadius: 6 }}
              >
                进入管理后台
              </Button>
            )}
            <Space>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#1677ff' }} />
              <span style={{ color: '#333', fontWeight: 500 }}>
                {user?.real_name || user?.username || '会员用户'}
              </span>
            </Space>
            <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout} danger>
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, minHeight: 280, background: colorBgContainer, borderRadius: borderRadiusLG }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default ClientLayout;
