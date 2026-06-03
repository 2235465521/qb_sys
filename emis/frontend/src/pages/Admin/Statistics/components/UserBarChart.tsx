import React from 'react';
import { Card, Empty } from 'antd';
import { BarChartOutlined } from '@ant-design/icons';

interface TopUser {
  username: string;
  real_name: string;
  count: number;
}

interface UserBarChartProps {
  topUsers?: TopUser[];
}

const UserBarChart: React.FC<UserBarChartProps> = ({ topUsers = [] }) => {
  if (topUsers.length === 0) {
    return (
      <Card title={<span style={{ fontWeight: 'bold' }}><BarChartOutlined /> 活跃用户排行</span>} style={{ height: 380, borderRadius: 16 }}>
        <Empty description="暂无活跃用户数据" style={{ marginTop: 80 }} />
      </Card>
    );
  }

  const width = 500;
  const height = 280;
  const paddingLeft = 110; // Extra room for usernames
  const paddingRight = 45; // Room for count label at end of bar
  const paddingTop = 20;

  const maxVal = Math.max(...topUsers.map(u => u.count), 1);
  const barHeight = 18;
  const gap = 12;

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><BarChartOutlined /> 系统用户活跃量榜 (Top 8)</span>} 
      style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
    >
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden' }}>
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} style={{ overflow: 'visible' }}>
          <defs>
            <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#722ed1" />
              <stop offset="100%" stopColor="#1890ff" />
            </linearGradient>
            <linearGradient id="topBarGrad" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ff4d4f" />
              <stop offset="100%" stopColor="#fa8c16" />
            </linearGradient>
          </defs>

          {topUsers.map((user, idx) => {
            const y = paddingTop + idx * (barHeight + gap);
            const barWidth = ((width - paddingLeft - paddingRight) * user.count) / maxVal;
            const displayName = user.real_name || user.username;
            
            // Medals for top 3
            const rankColor = idx === 0 ? '#d4af37' : idx === 1 ? '#c0c0c0' : idx === 2 ? '#cd7f32' : '#8c8c8c';
            const isTop3 = idx < 3;

            return (
              <g key={idx}>
                {/* Rank Number */}
                <circle cx={25} cy={y + barHeight / 2} r={9} fill={rankColor} />
                <text x={25} y={y + barHeight / 2 + 3.5} fontSize={10} fontWeight="bold" fill="#fff" textAnchor="middle">
                  {idx + 1}
                </text>

                {/* User Name */}
                <text 
                  x={45} 
                  y={y + barHeight / 2 + 4} 
                  fontSize={12} 
                  fontWeight={500}
                  fill="#444" 
                  textAnchor="start"
                  style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                >
                  {displayName.length > 8 ? `${displayName.substring(0, 7)}…` : displayName}
                </text>

                {/* Background Track */}
                <rect 
                  x={paddingLeft} 
                  y={y} 
                  width={width - paddingLeft - paddingRight} 
                  height={barHeight} 
                  rx={9} 
                  fill="#f5f5f5" 
                />

                {/* Filled Bar */}
                <rect 
                  x={paddingLeft} 
                  y={y} 
                  width={Math.max(barWidth, 12)} // Small min width so it is visible
                  height={barHeight} 
                  rx={9} 
                  fill={`url(${isTop3 ? '#topBarGrad' : '#barGrad'})`} 
                />

                {/* Value Label */}
                <text 
                  x={paddingLeft + Math.max(barWidth, 12) + 8} 
                  y={y + barHeight / 2 + 4} 
                  fontSize={11} 
                  fontWeight="bold" 
                  fill={isTop3 ? '#fa8c16' : '#1890ff'}
                  textAnchor="start"
                >
                  {user.count}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </Card>
  );
};

export default UserBarChart;
