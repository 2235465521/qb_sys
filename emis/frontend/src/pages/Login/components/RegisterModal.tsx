import React, { useState } from 'react';
import { Modal, Form, Input, Button, Typography, message, ConfigProvider } from 'antd';
import { UserOutlined, IdcardOutlined } from '@ant-design/icons';
import axios, { AxiosError } from 'axios';
import BrandLogo from '@/components/BrandLogo';

const { Text } = Typography;

interface RegisterModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

export const RegisterModal: React.FC<RegisterModalProps> = ({ open, onCancel, onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  const onFinish = async (values: { username: string; real_name: string }) => {
    setLoading(true);
    try {
      await axios.post('/api/auth/register/', {
        username: values.username,
        real_name: values.real_name,
      });
      
      message.success('账号注册成功！请使用注册账号进行登录');
      form.resetFields();
      onSuccess();
    } catch (error) {
      console.error('Register error:', error);
      const axiosError = error as AxiosError<{ detail?: string }>;
      const errorMsg = axiosError.response?.data?.detail || '注册失败，请检查填写信息是否合法或用户名是否已存在';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConfigProvider
      theme={{
        components: {
          Modal: {
            contentBg: 'rgba(0, 0, 0, 0.22)',
            headerBg: 'transparent',
            titleColor: '#ffffff',
          }
        }
      }}
    >
      <Modal
        open={open}
        onCancel={() => {
          form.resetFields();
          onCancel();
        }}
        footer={null}
        centered
        width={420}
        className="glass-modal"
        classNames={{ mask: 'glass-modal-mask' }}
        closeIcon={<span style={{ color: 'rgba(255, 255, 255, 0.55)', fontSize: 16 }}>✕</span>}
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
          <span style={{ 
            fontSize: 18, 
            color: '#ffffff', 
            fontWeight: 'bold', 
            letterSpacing: 2,
            display: 'block'
          }}>
            申请您的 EMIS 账号
          </span>
          <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, marginTop: 4, display: 'block' }}>
            Enterprise Management Information System
          </Text>
        </div>

        <Form
          form={form}
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
              className="minimal-input-wrapper"
              prefix={<UserOutlined style={{ color: 'rgba(255,255,255,0.7)', marginRight: 8 }} />} 
              placeholder="登录账号 (英文/数字组合)" 
            />
          </Form.Item>

          <Form.Item
            name="real_name"
            rules={[{ required: true, message: '请输入您的真实姓名/企业称呼' }]}
          >
            <Input 
              className="minimal-input-wrapper"
              prefix={<IdcardOutlined style={{ color: 'rgba(255,255,255,0.7)', marginRight: 8 }} />} 
              placeholder="真实姓名 / 企业称呼" 
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
                boxShadow: '0 8px 20px rgba(79, 172, 254, 0.3)',
                fontWeight: 'bold',
                marginTop: 15,
                letterSpacing: 1
              }}
            >
              确认注册 REGISTER
            </Button>
          </Form.Item>
          
          <div style={{ textAlign: 'center', marginTop: 10 }}>
            <span 
              style={{ fontSize: 12, cursor: 'pointer', color: 'rgba(255,255,255,0.6)', transition: 'color 0.3s' }}
              onClick={() => {
                form.resetFields();
                onCancel();
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = '#00f2fe'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'rgba(255,255,255,0.6)'; }}
            >
              返回登录
            </span>
          </div>
        </Form>
      </Modal>
    </ConfigProvider>
  );
};
