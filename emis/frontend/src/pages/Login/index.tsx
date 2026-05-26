import React from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';

const { Title, Text } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(false);
  const queryClient = useQueryClient();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const response = await axios.post('/api/auth/login/', {
        username: values.username,
        password: values.password
      });
      
      const { access, refresh } = response.data;
      localStorage.setItem('access_token', access);
      localStorage.setItem('refresh_token', refresh);
      queryClient.clear();
      
      // 获取用户信息，依据角色进行分流重定向
      const userRes = await axios.get('/api/auth/me/', {
        headers: { Authorization: `Bearer ${access}` }
      });
      const user = userRes.data;
      
      message.success(`登录成功，欢迎回来，${user.real_name || user.username}`);
      
      if (['superadmin', 'admin', 'operator'].includes(user.role)) {
        navigate('/admin/dashboard');
      } else {
        navigate('/client/search');
      }
    } catch (error: any) {
      console.error('Login error:', error);
      const errorMsg = error.response?.data?.detail || '登录失败，请检查账号密码';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center',
      background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* 背景装饰球 */}
      <div style={{ position: 'absolute', width: 400, height: 400, background: 'rgba(255,255,255,0.1)', borderRadius: '50%', top: -100, right: -100 }} />
      <div style={{ position: 'absolute', width: 300, height: 300, background: 'rgba(255,255,255,0.05)', borderRadius: '50%', bottom: -50, left: -50 }} />

      <Card 
        bordered={false}
        style={{ 
          width: 400, 
          borderRadius: 16, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          backdropFilter: 'blur(10px)',
          background: 'rgba(255, 255, 255, 0.95)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ 
            width: 64, height: 64, background: '#1890ff', borderRadius: 12, 
            display: 'inline-flex', justifyContent: 'center', alignItems: 'center',
            marginBottom: 16, boxShadow: '0 4px 12px rgba(24,144,255,0.3)'
          }}>
            <SafetyCertificateOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: 0 }}>EMIS 企业管理系统</Title>
          <Text type="secondary">Enterprise Management Information System</Text>
        </div>

        <Form
          name="login"
          size="large"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名 / 管理员账号" />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading} style={{ height: 45, borderRadius: 8 }}>
              立即登录
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Text type="secondary" style={{ fontSize: 12, cursor: 'pointer' }}>忘记密码？</Text>
              <Text 
                type="secondary" 
                style={{ fontSize: 12, cursor: 'pointer', color: '#1890ff' }}
                onClick={() => navigate('/register')}
              >
                申请账号
              </Text>
            </Space>
          </div>
        </Form>
      </Card>
    </div>
  );
};

export default LoginPage;
