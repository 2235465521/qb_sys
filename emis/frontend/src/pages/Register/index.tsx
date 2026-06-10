import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Space } from 'antd';
import { UserOutlined, IdcardOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const { Title, Text } = Typography;

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      await axios.post('/api/auth/register/', {
        username: values.username,
        real_name: values.real_name,
      });
      
      message.success('账号注册成功！正在为您跳转到登录页...');
      setTimeout(() => {
        navigate('/login');
      }, 1500);
    } catch (error: any) {
      console.error('Register error:', error);
      const errorMsg = error.response?.data?.detail || '注册失败，请检查填写信息是否合法或用户名是否已存在';
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
      backgroundColor: '#040b16',
      backgroundImage: `url('/login-bg.jpg')`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat',
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* Glow effects to blend with light premium theme */}
      <div style={{ position: 'absolute', width: 600, height: 600, background: 'radial-gradient(circle, rgba(22,163,74,0.04) 0%, transparent 70%)', borderRadius: '50%', top: -200, right: -200, pointerEvents: 'none' }} />
      <div style={{ position: 'absolute', width: 500, height: 500, background: 'radial-gradient(circle, rgba(22,163,74,0.03) 0%, transparent 70%)', borderRadius: '50%', bottom: -150, left: -150, pointerEvents: 'none' }} />

      <Card 
        bordered={false}
        style={{ 
          width: 420, 
          borderRadius: 20, 
          boxShadow: '0 20px 40px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.6)',
          backdropFilter: 'blur(20px)',
          background: 'rgba(255, 255, 255, 0.85)',
          border: '1px solid rgba(255, 255, 255, 0.7)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ 
            width: 64, height: 64, background: 'rgba(22,163,74,0.1)', borderRadius: 12, 
            display: 'inline-flex', justifyContent: 'center', alignItems: 'center',
            marginBottom: 16, border: '1px solid rgba(22,163,74,0.2)',
            boxShadow: '0 4px 16px rgba(22,163,74,0.08)'
          }}>
            <SafetyCertificateOutlined style={{ fontSize: 32, color: '#15803d' }} />
          </div>
          <Title level={3} style={{ margin: 0, color: '#1e293b' }}>申请您的 EMIS 账号</Title>
          <Text style={{ color: '#64748b', fontSize: 13, marginTop: 4, display: 'block' }}>Enterprise Management Information System</Text>
        </div>

        <Form
          name="register"
          size="large"
          onFinish={onFinish}
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入您要注册的登录账号' },
              { min: 2, message: '账号长度至少2位' }
            ]}
          >
            <Input 
              prefix={<UserOutlined style={{ color: '#15803d' }} />} 
              placeholder="登录账号 (英文/数字组合)" 
              style={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#1e293b', borderRadius: 8 }}
            />
          </Form.Item>

          <Form.Item
            name="real_name"
            rules={[{ required: true, message: '请输入您的真实姓名/企业称呼' }]}
          >
            <Input 
              prefix={<IdcardOutlined style={{ color: '#15803d' }} />} 
              placeholder="真实姓名 / 企业称呼" 
              style={{ background: '#ffffff', border: '1px solid #e2e8f0', color: '#1e293b', borderRadius: 8 }}
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
                backgroundColor: '#15803d',
                borderColor: '#15803d',
                boxShadow: '0 8px 16px rgba(21, 128, 61, 0.15)',
                fontWeight: 'bold'
              }}
            >
              确认注册并生成账号
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Text type="secondary" style={{ color: '#64748b' }}>已有账号？</Text>
              <Text 
                style={{ fontSize: 13, cursor: 'pointer', color: '#15803d', fontWeight: 'bold' }}
                onClick={() => navigate('/login')}
              >
                返回安全登录
              </Text>
            </Space>
          </div>
        </Form>
      </Card>
    </div>
  );
};

export default RegisterPage;
