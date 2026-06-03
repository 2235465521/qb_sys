import React from 'react';
import { Row, Col, Card, Statistic, Tooltip } from 'antd';
import { 
  InteractionOutlined, 
  FireOutlined, 
  UserOutlined, 
  WarningOutlined
} from '@ant-design/icons';

interface StatsCardsProps {
  totalHits: number;
  todayHits: number;
  activeUsersToday: number;
  activeUsersWeek: number;
  dauRate: number;
  wauRate: number;
  totalWarnings: number;
}

const StatsCards: React.FC<StatsCardsProps> = ({
  totalHits,
  todayHits,
  activeUsersToday,
  activeUsersWeek,
  dauRate,
  wauRate,
  totalWarnings
}) => {
  const cardStyle = {
    borderRadius: 16,
    boxShadow: '0 4px 20px rgba(0,0,0,0.02)',
    border: '1px solid #f0f0f0',
    transition: 'all 0.3s ease',
    cursor: 'default',
  };

  const onMouseEnter = (e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.transform = 'translateY(-4px)';
    e.currentTarget.style.boxShadow = '0 8px 30px rgba(0,0,0,0.06)';
  };

  const onMouseLeave = (e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.transform = 'translateY(0)';
    e.currentTarget.style.boxShadow = '0 4px 20px rgba(0,0,0,0.02)';
  };

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} lg={6}>
        <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} style={{ transition: 'all 0.3s' }}>
          <Card style={cardStyle} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: '#888', fontWeight: 500 }}>系统累计使用量</span>}
              value={totalHits}
              prefix={<InteractionOutlined style={{ color: '#1890ff', marginRight: 8 }} />}
              valueStyle={{ fontWeight: 700, color: '#333' }}
            />
            <div style={{ marginTop: 8, fontSize: 13, color: '#999' }}>
              总 API 请求次数
            </div>
          </Card>
        </div>
      </Col>

      <Col xs={24} sm={12} lg={6}>
        <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} style={{ transition: 'all 0.3s' }}>
          <Card style={cardStyle} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: '#888', fontWeight: 500 }}>今日活跃使用量</span>}
              value={todayHits}
              prefix={<FireOutlined style={{ color: '#52c41a', marginRight: 8 }} />}
              valueStyle={{ fontWeight: 700, color: '#333' }}
            />
            <div style={{ marginTop: 8, fontSize: 13, color: '#999' }}>
              今日已处理请求数
            </div>
          </Card>
        </div>
      </Col>

      <Col xs={24} sm={12} lg={6}>
        <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} style={{ transition: 'all 0.3s' }}>
          <Card style={cardStyle} bodyStyle={{ padding: 20 }}>
            <Tooltip title={`本周活跃人数: ${activeUsersWeek} 人，周活跃率: ${wauRate}%`}>
              <Statistic
                title={<span style={{ color: '#888', fontWeight: 500 }}>日活跃率 (DAU)</span>}
                value={dauRate}
                precision={1}
                suffix="%"
                prefix={<UserOutlined style={{ color: '#722ed1', marginRight: 8 }} />}
                valueStyle={{ fontWeight: 700, color: '#333' }}
              />
            </Tooltip>
            <div style={{ marginTop: 8, fontSize: 13, color: '#999', display: 'flex', justifyContent: 'space-between' }}>
              <span>今日活跃: {activeUsersToday} 人</span>
              <span style={{ color: '#722ed1', fontWeight: 500 }}>周活跃: {activeUsersWeek} 人</span>
            </div>
          </Card>
        </div>
      </Col>

      <Col xs={24} sm={12} lg={6}>
        <div onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} style={{ transition: 'all 0.3s' }}>
          <Card style={cardStyle} bodyStyle={{ padding: 20 }}>
            <Statistic
              title={<span style={{ color: '#888', fontWeight: 500 }}>系统安全警报</span>}
              value={totalWarnings}
              prefix={<WarningOutlined style={{ color: totalWarnings > 0 ? '#ff4d4f' : '#faad14', marginRight: 8 }} />}
              valueStyle={{ fontWeight: 700, color: totalWarnings > 0 ? '#ff4d4f' : '#333' }}
            />
            <div style={{ marginTop: 8, fontSize: 13, color: '#999' }}>
              高频恶意爬取/异常预警
            </div>
          </Card>
        </div>
      </Col>
    </Row>
  );
};

export default StatsCards;
