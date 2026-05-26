import React from 'react';
import { Card, Progress } from 'antd';
import { PieChartOutlined } from '@ant-design/icons';

interface DistributionProps {
  distribution?: { type: string; value: number }[];
}

const DistributionCard: React.FC<DistributionProps> = ({ distribution = [] }) => {
  const total = distribution.reduce((sum, item) => sum + item.value, 0);

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><PieChartOutlined /> 标准分类占比</span>}
      style={{ height: '100%', borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {distribution.map((item, idx) => {
          const percent = total > 0 ? Math.round((item.value / total) * 100) : 0;
          return (
            <div key={idx}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 500, color: '#333' }}>{item.type}</span>
                <span style={{ color: '#666', fontSize: 12 }}>{item.value} 份 ({percent}%)</span>
              </div>
              <Progress 
                percent={percent} 
                showInfo={false} 
                strokeColor={{
                  '0%': idx === 0 ? '#1890ff' : idx === 1 ? '#52c41a' : idx === 2 ? '#faad14' : '#722ed1',
                  '100%': idx === 0 ? '#096dd9' : idx === 1 ? '#389e0d' : idx === 2 ? '#d46b08' : '#531dab',
                }}
                strokeWidth={8}
                style={{ margin: 0 }}
              />
            </div>
          );
        })}
      </div>
    </Card>
  );
};

export default DistributionCard;
