import React, { useState } from 'react';
import { Layout, Menu, Button, theme, Space, Avatar, Tag } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  LogoutOutlined,
  UserOutlined,
  CloudServerOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useQueryClient } from '@tanstack/react-query';
import { adminMenuItems } from './AdminMenuConfig';

const { Header, Sider, Content } = Layout;

const AdminLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const handleLogout = () => {
    localStorage.clear();
    queryClient.clear();
    navigate('/login');
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark" style={{ boxShadow: '2px 0 8px 0 rgba(0,0,0,.15)' }}>
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold', fontSize: collapsed ? 12 : 20, color: '#fff', background: '#002140' }}>
          {collapsed ? <CloudServerOutlined /> : 'EMIS 管理后台'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={['core_business', 'customer_marketing']}
          items={adminMenuItems}
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
            <Button 
              type="default" 
              onClick={() => navigate('/client')}
              style={{ borderRadius: 6 }}
            >
              返回前台门户
            </Button>
            {user?.role === 'superadmin' && <Tag color="red">超级管理员</Tag>}
            {user?.role === 'admin' && <Tag color="blue">管理员</Tag>}
            {user?.role === 'operator' && <Tag color="orange">运营操作员</Tag>}
            <Space>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#87d068' }} />
              <span style={{ fontWeight: 'bold', color: '#333' }}>
                {user?.real_name || user?.username || 'Admin'}
              </span>
            </Space>
            <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout} danger style={{ padding: '0 8px' }}>
              安全退出
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

export default AdminLayout;
