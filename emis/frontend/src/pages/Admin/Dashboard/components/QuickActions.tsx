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
      <Col xs={24} md={12}>
        <Card 
          title={<span style={{ fontWeight: 'bold', fontSize: 16 }}>快捷管理通道</span>}
          style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0' }}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Button 
              type="primary" 
              icon={<PlusOutlined />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/admin/companies')}
            >
              录入企业标准
            </Button>
            <Button 
              type="default" 
              icon={<FileExcelOutlined style={{ color: '#52c41a' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/admin/companies')}
            >
              Excel 导入企业
            </Button>
            <Button 
              type="default" 
              icon={<MessageOutlined style={{ color: '#1890ff' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/admin/sms-templates')}
            >
              模板管理配置
            </Button>
            <Button 
              type="dashed" 
              icon={<SyncOutlined spin style={{ color: '#722ed1' }} />} 
              size="large"
              style={{ height: 50, borderRadius: 8 }}
              onClick={() => navigate('/client/members')}
            >
              进入会员中心
            </Button>
          </div>
        </Card>
      </Col>
      
      <Col xs={24} md={12}>
        <Card 
          title={<span style={{ fontWeight: 'bold', fontSize: 16 }}>系统底层监控看板</span>}
          style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0' }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <DatabaseOutlined style={{ color: '#1890ff' }} />
                <span style={{ fontWeight: 500 }}>Django 后端运行状态</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />}>ONLINE</Tag>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <SyncOutlined spin style={{ color: '#722ed1' }} />
                <span style={{ fontWeight: 500 }}>Celery 异步队列管理器</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />}>RUNNING</Tag>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space>
                <DatabaseOutlined style={{ color: '#52c41a' }} />
                <span style={{ fontWeight: 500 }}>MySQL 8.0 数据库服务</span>
              </Space>
              <Tag color="success" icon={<CheckCircleOutlined />}>CONNECTED</Tag>
            </div>
          </div>
        </Card>
      </Col>
    </Row>
  );
};

export default QuickActions;
