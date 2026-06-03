import React from 'react';
import { Card, Empty } from 'antd';
import { ClockCircleOutlined } from '@ant-design/icons';

interface HourStat {
  hour: string;
  count: number;
}

interface TimeDistributionChartProps {
  hourlyDistribution?: HourStat[];
}

const TimeDistributionChart: React.FC<TimeDistributionChartProps> = ({ hourlyDistribution = [] }) => {
  if (hourlyDistribution.length === 0) {
    return (
      <Card title={<span style={{ fontWeight: 'bold' }}><ClockCircleOutlined /> 每日使用时间段分布</span>} style={{ height: 380, borderRadius: 16 }}>
        <Empty description="暂无时间段分布数据" style={{ marginTop: 80 }} />
      </Card>
    );
  }

  const width = 600;
  const height = 280;
  const paddingLeft = 40;
  const paddingRight = 20;
  const paddingTop = 30;
  const paddingBottom = 40;

  const maxVal = Math.max(...hourlyDistribution.map(h => h.count), 5);
  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;
  const colWidth = chartWidth / 24;

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><ClockCircleOutlined /> 每日 24 小时活跃时段分布</span>} 
      style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
    >
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="colGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1890ff" />
              <stop offset="100%" stopColor="#87e8de" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio, idx) => {
            const y = paddingTop + ratio * chartHeight;
            const gridVal = Math.round(maxVal - ratio * maxVal);
            return (
              <g key={idx}>
                <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke="#f5f5f5" />
                <text x={paddingLeft - 8} y={y + 4} fontSize={10} fill="#999" textAnchor="end">{gridVal}</text>
              </g>
            );
          })}

          {/* Draw Columns */}
          {hourlyDistribution.map((item, idx) => {
            const colHeight = (chartHeight * item.count) / maxVal;
            const x = paddingLeft + idx * colWidth + 2; // +2 for spacing
            const y = height - paddingBottom - colHeight;
            const w = colWidth - 4; // Spacing between columns

            const hourNum = parseInt(item.hour.split(':')[0], 10);
            const showLabel = hourNum % 4 === 0;

            return (
              <g key={idx}>
                {/* Column */}
                <rect 
                  x={x} 
                  y={y} 
                  width={Math.max(w, 2)} 
                  height={Math.max(colHeight, 1)} 
                  rx={2}
                  fill="url(#colGrad)" 
                />
                
                {/* Column Hover Text (if count > 0, show a small label on top) */}
                {item.count > 0 && (
                  <text 
                    x={x + w / 2} 
                    y={y - 6} 
                    fontSize={9} 
                    fontWeight="bold" 
                    fill="#1890ff" 
                    textAnchor="middle"
                  >
                    {item.count}
                  </text>
                )}

                {/* X Axis labels (Only show every 4 hours to avoid congestion) */}
                {showLabel && (
                  <g>
                    <line x1={x + w / 2} y1={height - paddingBottom} x2={x + w / 2} y2={height - paddingBottom + 4} stroke="#ccc" />
                    <text 
                      x={x + w / 2} 
                      y={height - 18} 
                      fontSize={10} 
                      fill="#888" 
                      textAnchor="middle"
                    >
                      {item.hour}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
};

export default TimeDistributionChart;
