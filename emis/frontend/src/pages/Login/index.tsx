import React from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios, { AxiosError } from 'axios';
import { useQueryClient } from '@tanstack/react-query';
import BrandLogo from '@/components/BrandLogo';
import { RegisterModal } from './components/RegisterModal';

const { Text } = Typography;

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(false);
  const [registerOpen, setRegisterOpen] = React.useState(false);
  const queryClient = useQueryClient();

  const onFinish = async (values: { username?: string; password?: string }) => {
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
    } catch (error) {
      console.error('Login error:', error);
      const axiosError = error as AxiosError<{ detail?: string }>;
      const errorMsg = axiosError.response?.data?.detail || '登录失败，请检查账号密码';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const minimalInputStyle = `
    .minimal-input-wrapper {
      background: transparent !important;
      border: none !important;
      border-bottom: 1px solid rgba(255, 255, 255, 0.4) !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      padding-left: 0;
      padding-right: 0;
      transition: all 0.3s;
    }
    .minimal-input-wrapper:hover, .minimal-input-wrapper-focused {
      border-bottom: 1px solid #00f2fe !important;
    }
    .minimal-input-wrapper input {
      background: transparent !important;
      color: white !important;
    }
    .minimal-input-wrapper input::placeholder {
      color: rgba(255, 255, 255, 0.5) !important;
    }
    .ant-input-password-icon {
      color: rgba(255, 255, 255, 0.5) !important;
    }
    .ant-input-password-icon:hover {
      color: #ffffff !important;
    }
    .glass-modal .ant-modal-content {
      background: rgba(0, 0, 0, 0.45) !important;
      backdrop-filter: blur(16px) !important;
      -webkit-backdrop-filter: blur(16px) !important;
      border: 1px solid rgba(255, 255, 255, 0.12) !important;
      border-radius: 16px !important;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5) !important;
      padding: 36px 28px !important;
    }
    .glass-modal-mask {
      backdrop-filter: blur(10px) !important;
      -webkit-backdrop-filter: blur(10px) !important;
      background-color: rgba(4, 11, 22, 0.45) !important;
    }
  `;

  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center',
      backgroundColor: '#040b16',
      backgroundImage: `url('/login-bg.jpg')`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      overflow: 'hidden',
      position: 'relative'
    }}>
      <style>{minimalInputStyle}</style>
      
      <Card 
        bordered={false}
        style={{ 
          width: 440, 
          borderRadius: 16, 
          boxShadow: '0 15px 35px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(12px)',
          background: 'rgba(0, 0, 0, 0.35)',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          {/* Brand Logo Container */}
          <div style={{ 
            width: 96, height: 96, 
            background: 'rgba(255, 255, 255, 0.05)', 
            borderRadius: '50%', 
            display: 'inline-flex', justifyContent: 'center', alignItems: 'center',
            marginBottom: 20, border: '1px solid rgba(255, 255, 255, 0.15)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
            backdropFilter: 'blur(4px)'
          }}>
            <BrandLogo width={72} height={72} style={{ filter: 'drop-shadow(0 0 8px rgba(255,255,255,0.3))' }} />
          </div>

          {/* Typography Headers */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
            <span style={{ 
              fontSize: 18, 
              color: '#ffffff', 
              fontWeight: 'bold', 
              letterSpacing: 2, 
            }}>
              中科标准企业管理信息系统
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
              <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 13, display: 'block', fontWeight: 500 }}>
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
              className="minimal-input-wrapper"
              prefix={<UserOutlined style={{ color: 'rgba(255,255,255,0.7)', marginRight: 8 }} />} 
              placeholder="用户名 / 管理员账号" 
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password 
              className="minimal-input-wrapper"
              prefix={<LockOutlined style={{ color: 'rgba(255,255,255,0.7)', marginRight: 8 }} />} 
              placeholder="密码" 
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
                borderRadius: 25, 
                background: 'linear-gradient(90deg, #00f2fe 0%, #4facfe 100%)', 
                border: 'none',
                boxShadow: '0 8px 20px rgba(79, 172, 254, 0.4)',
                fontWeight: 'bold',
                marginTop: 10,
                letterSpacing: 1
              }}
            >
              登录 LOGIN
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Text style={{ fontSize: 12, cursor: 'pointer', color: 'rgba(255,255,255,0.6)' }}>忘记密码？</Text>
              <span 
                style={{ fontSize: 12, cursor: 'pointer', color: '#00f2fe', fontWeight: 'bold' }}
                onClick={() => setRegisterOpen(true)}
              >
                申请账号
              </span>
            </Space>
          </div>
        </Form>
      </Card>

      <RegisterModal
        open={registerOpen}
        onCancel={() => setRegisterOpen(false)}
        onSuccess={() => setRegisterOpen(false)}
      />
    </div>
  );
};

export default LoginPage;
