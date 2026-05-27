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
import { Badge, Popover, List, Progress } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useTaskContext } from '@/store/TaskContext';

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

  const { tasks, clearDoneTasks } = useTaskContext();
  
  const runningTasks = tasks.filter(t => t.status === 'running');
  
  const tasksPopoverContent = (
    <div style={{ width: 300 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontWeight: 'bold' }}>任务中心</span>
        <Button type="link" size="small" onClick={clearDoneTasks} style={{ padding: 0 }}>清除已完成</Button>
      </div>
      <List
        dataSource={tasks}
        locale={{ emptyText: '暂无后台任务' }}
        renderItem={item => (
          <List.Item>
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: 13 }} title={item.name}>{item.name.length > 15 ? item.name.substring(0, 15) + '...' : item.name}</span>
                <span style={{ fontSize: 12, color: item.status === 'failed' ? '#ff4d4f' : item.status === 'done' ? '#52c41a' : '#1890ff' }}>
                  {item.status === 'running' ? '打包中' : item.status === 'done' ? '已完成' : '失败'}
                </span>
              </div>
              <Progress percent={item.progress} status={item.status === 'failed' ? 'exception' : item.status === 'done' ? 'success' : 'active'} size="small" />
            </div>
          </List.Item>
        )}
      />
    </div>
  );

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
            <Popover content={tasksPopoverContent} trigger="click" placement="bottomRight">
              <Badge count={runningTasks.length} size="small">
                <Button type="text" icon={<BellOutlined style={{ fontSize: 18 }} />} />
              </Badge>
            </Popover>
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
