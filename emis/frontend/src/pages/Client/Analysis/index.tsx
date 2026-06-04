import React, { useState, useEffect } from 'react';
import { Row, Col, message } from 'antd';
import ReverseTracer from './components/ReverseTracer';
import NationalLeaderboard from './components/NationalLeaderboard';
import apiClient from '@/api/client';

const ReferenceAnalysisPage: React.FC = () => {
  const [rankData, setRankData] = useState<any[]>([]);
  const [rankLoading, setRankLoading] = useState(false);

  const fetchRanking = async () => {
    setRankLoading(true);
    try {
      const { data } = await apiClient.get<{ results: any[] }>('/client/analysis/citation-rank/', {
        params: { limit: 100 }
      });
      setRankData(data.results || []);
    } catch (err: any) {
      console.error(err);
      message.error('加载国标引用排行榜数据失败');
    } finally {
      setRankLoading(false);
    }
  };

  useEffect(() => {
    fetchRanking();
  }, []);

  return (
    <div className="reference-analysis-page" style={{ padding: '4px' }}>
      <Row gutter={24} align="stretch">
        {/* 左侧：企标反向溯源定位 */}
        <Col xs={24} lg={12} style={{ display: 'flex', flexDirection: 'column' }}>
          <ReverseTracer />
        </Col>

        {/* 右侧：热度排行榜 */}
        <Col xs={24} lg={12} style={{ display: 'flex', flexDirection: 'column' }}>
          <NationalLeaderboard
            data={rankData}
            loading={rankLoading}
          />
        </Col>
      </Row>
    </div>
  );
};

export default ReferenceAnalysisPage;
