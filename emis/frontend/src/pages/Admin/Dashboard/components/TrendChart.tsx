import React from 'react';
import { Card, Empty } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';

interface TrendChartProps {
  trend?: { month: string; count: number }[];
}

const TrendChart: React.FC<TrendChartProps> = ({ trend = [] }) => {
  if (trend.length === 0) {
    return (
      <Card title={<span style={{ fontWeight: 'bold' }}><LineChartOutlined /> 企业入库增长趋势</span>} style={{ height: 350, borderRadius: 12 }}>
        <Empty description="暂无趋势数据" style={{ marginTop: 50 }} />
      </Card>
    );
  }

  const width = 500;
  const height = 220;
  const paddingX = 40;
  const paddingY = 30;

  const maxVal = Math.max(...trend.map(t => t.count), 10);
  const minVal = 0;
  const range = maxVal - minVal;

  const points = trend.map((t, idx) => {
    const x = paddingX + (idx * (width - 2 * paddingX)) / (trend.length - 1);
    const y = height - paddingY - ((t.count - minVal) / range) * (height - 2 * paddingY);
    return { x, y, label: t.month, value: t.count };
  });

  const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - paddingY} L ${points[0].x} ${height - paddingY} Z`;

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><LineChartOutlined /> 企业入库增长趋势</span>} 
      style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.05)', border: '1px solid #f0f0f0' }}
    >
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1890ff" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#1890ff" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1890ff" />
              <stop offset="100%" stopColor="#722ed1" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const y = paddingY + ratio * (height - 2 * paddingY);
            const gridVal = Math.round(maxVal - ratio * range);
            return (
              <g key={idx}>
                <line x1={paddingX} y1={y} x2={width - paddingX} y2={y} stroke="#f0f0f0" strokeDasharray="3,3" />
                <text x={paddingX - 10} y={y + 4} fontSize={10} fill="#999" textAnchor="end">{gridVal}</text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#areaGrad)" />

          {/* Trend Line */}
          <path d={linePath} fill="none" stroke="url(#lineGrad)" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />

          {/* Glow spots */}
          {points.map((p, idx) => (
            <g key={idx}>
              <circle cx={p.x} cy={p.y} r={5} fill="#fff" stroke="#1890ff" strokeWidth={2} />
              <circle cx={p.x} cy={p.y} r={10} fill="#1890ff" fillOpacity={0.15} />
              
              {/* X Axis labels */}
              <text x={p.x} y={height - 10} fontSize={11} fill="#666" textAnchor="middle">{p.label}</text>
              
              {/* Floating value labels */}
              <text x={p.x} y={p.y - 12} fontSize={10} fontWeight="bold" fill="#1890ff" textAnchor="middle">{p.value}</text>
            </g>
          ))}
        </svg>
      </div>
    </Card>
  );
};

export default TrendChart;
