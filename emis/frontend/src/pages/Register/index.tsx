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
      background: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
      overflow: 'hidden',
      position: 'relative'
    }}>
      <div style={{ position: 'absolute', width: 400, height: 400, background: 'rgba(255,255,255,0.1)', borderRadius: '50%', top: -100, right: -100 }} />
      <div style={{ position: 'absolute', width: 300, height: 300, background: 'rgba(255,255,255,0.05)', borderRadius: '50%', bottom: -50, left: -50 }} />

      <Card 
        bordered={false}
        style={{ 
          width: 420, 
          borderRadius: 16, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
          backdropFilter: 'blur(10px)',
          background: 'rgba(255, 255, 255, 0.95)'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ 
            width: 64, height: 64, background: '#1890ff', borderRadius: 12, 
            display: 'inline-flex', justifyContent: 'center', alignItems: 'center',
            marginBottom: 16, boxShadow: '0 4px 12px rgba(24,144,255,0.3)'
          }}>
            <SafetyCertificateOutlined style={{ fontSize: 32, color: '#fff' }} />
          </div>
          <Title level={3} style={{ margin: 0 }}>申请您的 EMIS 账号</Title>
          <Text type="secondary">Enterprise Management Information System</Text>
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
            <Input prefix={<UserOutlined />} placeholder="登录账号 (英文/数字组合)" />
          </Form.Item>

          <Form.Item
            name="real_name"
            rules={[{ required: true, message: '请输入您的真实姓名/企业称呼' }]}
          >
            <Input prefix={<IdcardOutlined />} placeholder="真实姓名 / 企业称呼" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading} style={{ height: 45, borderRadius: 8 }}>
              确认注册并生成账号
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center' }}>
            <Space size="large">
              <Text type="secondary">已有账号？</Text>
              <Text 
                style={{ fontSize: 13, cursor: 'pointer', color: '#1890ff' }}
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
