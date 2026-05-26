import React from 'react';
import { Row, Col, Card } from 'antd';
import { BankOutlined, TeamOutlined, FileProtectOutlined, SendOutlined } from '@ant-design/icons';

interface StatsProps {
  totalCompanies: number;
  activeCompanies: number;
  totalMembers: number;
  activeMembers: number;
  totalStandards: number;
  enterpriseStandards: number;
  nationalStandards: number;
  totalSmsTasks: number;
  totalSentSms: number;
}

const StatsCards: React.FC<StatsProps> = ({
  totalCompanies,
  activeCompanies,
  totalMembers,
  activeMembers,
  totalStandards,
  enterpriseStandards,
  nationalStandards,
  totalSmsTasks,
  totalSentSms,
}) => {
  const cardData = [
    {
      title: '企业总数',
      value: totalCompanies,
      subValue: `活跃运行: ${activeCompanies}`,
      icon: <BankOutlined style={{ fontSize: 24, color: '#fff' }} />,
      grad: 'linear-gradient(135deg, #1890ff 0%, #722ed1 100%)',
      shadow: 'rgba(24, 144, 255, 0.2)',
    },
    {
      title: '会员总数',
      value: totalMembers,
      subValue: `活跃会员: ${activeMembers}`,
      icon: <TeamOutlined style={{ fontSize: 24, color: '#fff' }} />,
      grad: 'linear-gradient(135deg, #52c41a 0%, #13c2c2 100%)',
      shadow: 'rgba(82, 196, 26, 0.2)',
    },
    {
      title: '标准资产',
      value: totalStandards,
      subValue: `企标 ${enterpriseStandards} | 国标 ${nationalStandards}`,
      icon: <FileProtectOutlined style={{ fontSize: 24, color: '#fff' }} />,
      grad: 'linear-gradient(135deg, #faad14 0%, #ff4d4f 100%)',
      shadow: 'rgba(250, 173, 20, 0.2)',
    },
    {
      title: '短信推送',
      value: totalSmsTasks,
      subValue: `累计发送: ${totalSentSms} 条`,
      icon: <SendOutlined style={{ fontSize: 24, color: '#fff' }} />,
      grad: 'linear-gradient(135deg, #f759ab 0%, #722ed1 100%)',
      shadow: 'rgba(247, 89, 171, 0.2)',
    },
  ];

  return (
    <Row gutter={[24, 24]}>
      {cardData.map((c, idx) => (
        <Col xs={24} sm={12} md={6} key={idx}>
          <Card
            bordered={false}
            style={{
              background: c.grad,
              borderRadius: 16,
              boxShadow: `0 8px 24px ${c.shadow}`,
              overflow: 'hidden',
              position: 'relative',
              transition: 'transform 0.3s',
              cursor: 'pointer',
            }}
            bodyStyle={{ padding: '24px 20px' }}
            hoverable
          >
            {/* Decorative background shape */}
            <div style={{ position: 'absolute', right: -20, bottom: -20, width: 100, height: 100, borderRadius: '50%', background: 'rgba(255,255,255,0.1)' }} />
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: 14, fontWeight: 500 }}>{c.title}</span>
                <h1 style={{ color: '#fff', fontSize: 32, margin: '8px 0', fontWeight: 'bold', lineHeight: 1 }}>{c.value}</h1>
                <span style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12 }}>{c.subValue}</span>
              </div>
              <div style={{ background: 'rgba(255,255,255,0.2)', padding: 12, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {c.icon}
              </div>
            </div>
          </Card>
        </Col>
      ))}
    </Row>
  );
};

export default StatsCards;
