import React from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import BrandLogo from '@/components/BrandLogo';

const { Text } = Typography;

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
      background: 'radial-gradient(circle at center, #0e1e14 0%, #050806 100%)',
      backgroundImage: 'radial-gradient(circle at center, rgba(16, 32, 22, 0.9) 0%, rgba(5, 8, 6, 0.98) 100%), linear-gradient(rgba(82, 196, 26, 0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(82, 196, 26, 0.015) 1px, transparent 1px)',
      backgroundSize: '100% 100%, 30px 30px, 30px 30px',
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* Glow effects to blend with dark technology theme */}
      <div style={{ position: 'absolute', width: 600, height: 600, background: 'radial-gradient(circle, rgba(82,196,26,0.1) 0%, transparent 70%)', borderRadius: '50%', top: -200, right: -200, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', width: 500, height: 500, background: 'radial-gradient(circle, rgba(82,196,26,0.06) 0%, transparent 70%)', borderRadius: '50%', bottom: -150, left: -150, pointerEvents: 'none' }} />

      <Card 
        bordered={false}
        style={{ 
          width: 440, 
          borderRadius: 20, 
          boxShadow: '0 12px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)',
          backdropFilter: 'blur(16px)',
          background: 'rgba(15, 18, 16, 0.85)',
          border: '1px solid rgba(82, 196, 26, 0.15)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          {/* Brand Logo Container */}
          <div style={{ 
            width: 96, height: 96, background: 'rgba(82,196,26,0.1)', borderRadius: '50%', 
            display: 'inline-flex', justifyContent: 'center', alignItems: 'center',
            marginBottom: 20, border: '1px solid rgba(82,196,26,0.2)',
            boxShadow: '0 4px 20px rgba(82,196,26,0.15)'
          }}>
            <BrandLogo width={72} height={72} />
          </div>

          {/* Typography Headers */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span style={{ 
              fontSize: 16, 
              color: '#52c41a', 
              fontWeight: 'bold', 
              letterSpacing: 2, 
              textTransform: 'uppercase',
              opacity: 0.95
            }}>
              中科标准企业管理信息系统
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
              <Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: 13, display: 'block', fontWeight: 500 }}>
                Data-driven Enterprise Standard Management
              </Text>
            </div>
          </div>
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
            <Input 
              prefix={<UserOutlined style={{ color: '#52c41a' }} />} 
              placeholder="用户名 / 管理员账号" 
              style={{ 
                background: 'rgba(255,255,255,0.05)', 
                border: '1px solid rgba(255,255,255,0.1)', 
                color: '#fff',
                borderRadius: 8
              }}
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#52c41a' }} />} 
              placeholder="密码" 
              style={{ 
                background: 'rgba(255,255,255,0.05)', 
                border: '1px solid rgba(255,255,255,0.1)', 
                color: '#fff',
                borderRadius: 8
              }}
            />
          </Form.Item>

          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit" 
              block 
              loading={loading} 
              style={{ 
                height: 45, 
                borderRadius: 8, 
                backgroundColor: '#52c41a', 
                borderColor: '#52c41a',
                boxShadow: '0 4px 12px rgba(82,196,26,0.3)',
                fontWeight: 'bold'
              }}
            >
              立即登录
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Text style={{ fontSize: 12, cursor: 'pointer', color: 'rgba(255,255,255,0.45)' }}>忘记密码？</Text>
              <Text 
                style={{ fontSize: 12, cursor: 'pointer', color: '#52c41a', fontWeight: 'bold' }}
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
