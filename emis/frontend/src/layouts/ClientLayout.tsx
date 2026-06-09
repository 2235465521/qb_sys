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
  ClusterOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { useQueryClient } from '@tanstack/react-query';
import { Badge, Popover, List, Progress, Tooltip } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import { useTaskContext } from '@/store/TaskContext';
import BrandLogo from '@/components/BrandLogo';

const { Header, Sider, Content } = Layout;

const ClientLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAdmin } = useAuth();
  const queryClient = useQueryClient();
  const {
    token: { borderRadiusLG },
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
      key: '/client/graph',
      icon: <ClusterOutlined />,
      label: '标准知识图谱',
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

  const { tasks, clearDoneTasks, cancelTask, retryTask } = useTaskContext();
  
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
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'center' }}>
                <Tooltip title={item.name} color="rgba(0,0,0,0.85)">
                  <span style={{ fontSize: 13, fontWeight: 500 }}>{item.name.length > 15 ? item.name.substring(0, 15) + '...' : item.name}</span>
                </Tooltip>
                <Space size="small">
                  <span style={{ fontSize: 12, color: item.status === 'failed' ? '#ff4d4f' : item.status === 'done' ? '#52c41a' : '#1890ff' }}>
                    {item.status === 'running' ? '打包中' : item.status === 'done' ? '已完成' : '失败'}
                  </span>
                  {item.status === 'running' && (
                    <Button type="link" size="small" style={{ padding: 0, fontSize: 12, color: '#999' }} onClick={() => cancelTask(item.id)}>取消</Button>
                  )}
                  {item.status === 'failed' && (
                    <Space size={4}>
                      <Button 
                        type="link" 
                        size="small" 
                        style={{ padding: 0, fontSize: 12, color: '#1890ff' }} 
                        onClick={() => retryTask(item.id)}
                      >
                        重试
                      </Button>
                      <span style={{ color: '#ccc', fontSize: 10 }}>|</span>
                      <Button 
                        type="link" 
                        size="small" 
                        style={{ padding: 0, fontSize: 12, color: '#ff4d4f' }} 
                        onClick={() => cancelTask(item.id)}
                      >
                        删除
                      </Button>
                    </Space>
                  )}
                </Space>
              </div>
              <Progress percent={item.progress} status={item.status === 'failed' ? 'exception' : item.status === 'done' ? 'success' : 'active'} size="small" />
              {item.status === 'failed' && item.error && (
                <div style={{ fontSize: 11, color: '#ff4d4f', marginTop: 4, wordBreak: 'break-all' }}>
                  {item.error}
                </div>
              )}
            </div>
          </List.Item>
        )}
      />
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh', minWidth: 1200, overflowX: 'auto', background: '#f8fafc' }}>
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
          padding: '0 24px', 
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
          <Space size="large">
            {isAdmin && (
              <Button 
                type="primary" 
                ghost 
                onClick={() => navigate('/admin')}
                style={{ borderRadius: 8 }}
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
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#0d9488' }} />
              <span style={{ color: '#333', fontWeight: 500 }}>
                {user?.real_name || user?.username || '会员用户'}
              </span>
            </Space>
            <Button type="link" icon={<LogoutOutlined />} onClick={handleLogout} danger>
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: '24px', padding: 24, minHeight: 280, background: '#ffffff', borderRadius: borderRadiusLG, boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default ClientLayout;
