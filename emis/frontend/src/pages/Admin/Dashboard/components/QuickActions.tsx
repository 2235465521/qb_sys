import React from 'react';
import { Card, Row, Col, Button, Tag, Space } from 'antd';
import { 
  PlusOutlined, 
  FileExcelOutlined, 
  MessageOutlined, 
  CheckCircleOutlined,
  SyncOutlined,
  DatabaseOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

const QuickActions: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Row gutter={[24, 24]}>
      <Col xs={24} md={12} className="fade-in-up" style={{ animationDelay: '0.2s' }}>
        <Card 
          title={<span style={{ fontWeight: 600, fontSize: 16, color: '#0f172a' }}>快捷管理通道</span>}
          style={{ borderRadius: 16, boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)', border: '1px solid #f1f5f9' }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              size="large"
              style={{ 
                height: 50, 
                borderRadius: 8,
                background: 'linear-gradient(135deg, #0d9488 0%, #0f766e 100%)',
                borderColor: '#0d9488',
                boxShadow: '0 4px 12px rgba(13, 148, 120, 0.15)'
              }}
              onClick={() => navigate('/admin/companies')}
            >
              录入企业标准
            </Button>
            <Button 
              type="default" 
              icon={<FileExcelOutlined style={{ color: '#10b981' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/admin/companies')}
            >
              Excel 导入企业
            </Button>
            <Button 
              type="default" 
              icon={<MessageOutlined style={{ color: '#0ea5e9' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/admin/sms-templates')}
            >
              模板管理配置
            </Button>
            <Button 
              type="dashed" 
              icon={<SyncOutlined spin style={{ color: '#8b5cf6' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/client/members')}
            >
              进入会员中心
            </Button>
          </div>
        </Card>
      </Col>
      
      <Col xs={24} md={12} className="fade-in-up" style={{ animationDelay: '0.3s' }}>
        <Card 
          title={<span style={{ fontWeight: 600, fontSize: 16, color: '#0f172a' }}>系统底层监控看板</span>}
          style={{ borderRadius: 16, boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)', border: '1px solid #f1f5f9' }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <DatabaseOutlined style={{ color: '#0ea5e9' }} />
                <span style={{ fontWeight: 500, color: '#334155' }}>Django 后端运行状态</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />} style={{ borderRadius: 6, padding: '2px 8px' }}>ONLINE</Tag>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <SyncOutlined spin style={{ color: '#8b5cf6' }} />
                <span style={{ fontWeight: 500, color: '#334155' }}>Celery 异步队列管理器</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />} style={{ borderRadius: 6, padding: '2px 8px' }}>RUNNING</Tag>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <DatabaseOutlined style={{ color: '#10b981' }} />
                <span style={{ fontWeight: 500, color: '#334155' }}>MySQL 8.0 数据库服务</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />} style={{ borderRadius: 6, padding: '2px 8px' }}>CONNECTED</Tag>
            </div>
          </div>
        </Card>
      </Col>
    </Row>
  );
};

export default QuickActions;
