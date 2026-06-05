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
      title={<span style={{ fontWeight: 600, fontSize: 16, color: '#0f172a' }}><PieChartOutlined style={{ color: '#0d9488', marginRight: 6 }} /> 标准分类占比</span>}
      className="fade-in-up"
      style={{ height: '100%', borderRadius: 16, boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)', border: '1px solid #f1f5f9' }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {distribution.map((item, idx) => {
          const percent = total > 0 ? Math.round((item.value / total) * 100) : 0;
          return (
            <div key={idx}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 500, color: '#334155' }}>{item.type}</span>
                <span style={{ color: '#64748b', fontSize: 12 }}>{item.value} 份 ({percent}%)</span>
              </div>
              <Progress 
                percent={percent} 
                showInfo={false} 
                strokeColor={{
                  '0%': idx === 0 ? '#0d9488' : idx === 1 ? '#10b981' : idx === 2 ? '#f59e0b' : '#ec4899',
                  '100%': idx === 0 ? '#0f766e' : idx === 1 ? '#047857' : idx === 2 ? '#b45309' : '#be185d',
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
