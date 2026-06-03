import React from 'react';
import { Card, Empty } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';

interface TrendLineChartProps {
  trend?: { date: string; count: number }[];
}

const TrendLineChart: React.FC<TrendLineChartProps> = ({ trend = [] }) => {
  if (trend.length === 0) {
    return (
      <Card title={<span style={{ fontWeight: 'bold' }}><LineChartOutlined /> 系统使用频次趋势</span>} style={{ height: 380, borderRadius: 16 }}>
        <Empty description="暂无趋势数据" style={{ marginTop: 80 }} />
      </Card>
    );
  }

  const width = 600;
  const height = 280;
  const paddingLeft = 50;
  const paddingRight = 30;
  const paddingTop = 30;
  const paddingBottom = 40;

  const maxVal = Math.max(...trend.map(t => t.count), 10);
  const minVal = 0;
  const range = maxVal - minVal;

  const points = trend.map((t, idx) => {
    const x = paddingLeft + (idx * (width - paddingLeft - paddingRight)) / (trend.length - 1);
    const y = height - paddingBottom - ((t.count - minVal) / range) * (height - paddingTop - paddingBottom);
    return { x, y, label: t.date, value: t.count };
  });

  const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${height - paddingBottom} L ${points[0].x} ${height - paddingBottom} Z`;

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><LineChartOutlined /> 近15天系统操作活跃量趋势</span>} 
      style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
    >
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="usageAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1890ff" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#1890ff" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="usageLineGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1890ff" />
              <stop offset="100%" stopColor="#52c41a" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const y = paddingTop + ratio * (height - paddingTop - paddingBottom);
            const gridVal = Math.round(maxVal - ratio * range);
            return (
              <g key={idx}>
                <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#f5f5f5" strokeDasharray="3,3" />
                <text x={paddingLeft - 12} y={y + 4} fontSize={11} fill="#999" textAnchor="end">{gridVal}</text>
              </g>
            );
          })}

          {/* Area Fill */}
          <path d={areaPath} fill="url(#usageAreaGrad)" />

          {/* Trend Line */}
          <path d={linePath} fill="none" stroke="url(#usageLineGrad)" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round" />

          {/* Glow spots */}
          {points.map((p, idx) => {
            // Only draw dots for endpoints and every second point if congested, but 15 points fits fine
            return (
              <g key={idx}>
                <circle cx={p.x} cy={p.y} r={4} fill="#fff" stroke="#1890ff" strokeWidth={2.5} />
                <circle cx={p.x} cy={p.y} r={8} fill="#1890ff" fillOpacity={0.12} />
                
                {/* X Axis labels */}
                {idx % 2 === 0 && (
                  <text x={p.x} y={height - 15} fontSize={10} fill="#888" textAnchor="middle">{p.label}</text>
                )}
                
                {/* Floating value labels (on hover or always for simplicity if they look neat) */}
                <text x={p.x} y={p.y - 12} fontSize={10} fontWeight="bold" fill="#096dd9" textAnchor="middle">{p.value}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
};

export default TrendLineChart;
