import React from 'react';
import { Row, Col } from 'antd';
import { LineChartOutlined } from '@ant-design/icons';
import { useAnalysisData } from '@/hooks/useAnalysisData';
import ReverseTracer from './components/ReverseTracer';
import NationalLeaderboard from './components/NationalLeaderboard';

const ReferenceAnalysisPage: React.FC = () => {
  const { rankQuery } = useAnalysisData();

  return (
    <div className="reference-analysis-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
      <div 
        style={{ 
          marginBottom: 24, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 4px 15px rgba(0,0,0,0.03)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#009688', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <LineChartOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#004d40', fontWeight: 'bold' }}>规范性引用记录系统</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#00796b' }}>
              支持根据企标反向追踪定位其起草企业的信用代码及法人画像，并同步展示底层国家标准热度排行。
            </p>
          </div>
        </div>
      </div>

      <Row gutter={24}>
        {/* 左侧：企标反向溯源定位 */}
        <Col xs={24} lg={12}>
          <ReverseTracer />
        </Col>

        {/* 右侧：热度排行榜 */}
        <Col xs={24} lg={12}>
          <NationalLeaderboard
            data={rankQuery.data || []}
            loading={rankQuery.isLoading}
          />
        </Col>
      </Row>
    </div>
  );
};

export default ReferenceAnalysisPage;
