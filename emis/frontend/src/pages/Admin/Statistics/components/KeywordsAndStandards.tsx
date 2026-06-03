import React from 'react';
import { Row, Col, Card, Progress, List, Tag, Empty } from 'antd';
import { SearchOutlined, BookOutlined, FireOutlined } from '@ant-design/icons';

interface KeywordStat {
  keyword: string;
  count: number;
}

interface StandardStat {
  id: string;
  title: string;
  count: number;
}

interface KeywordsAndStandardsProps {
  hotKeywords?: KeywordStat[];
  hotStandards?: StandardStat[];
}

const KeywordsAndStandards: React.FC<KeywordsAndStandardsProps> = ({
  hotKeywords = [],
  hotStandards = []
}) => {
  // Calculate total search keyword hits to calculate percentages
  const totalKeywordHits = hotKeywords.reduce((sum, k) => sum + k.count, 0);

  return (
    <Row gutter={[16, 16]}>
      {/* Left Column: Hot Keywords */}
      <Col xs={24} md={12}>
        <Card 
          title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><SearchOutlined /> 用户搜索热词 Top 10</span>}
          style={{ height: '100%', borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
          bodyStyle={{ padding: 24 }}
        >
          {hotKeywords.length === 0 ? (
            <Empty description="暂无搜索数据" style={{ padding: '40px 0' }} />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {hotKeywords.map((item, idx) => {
                const percent = totalKeywordHits > 0 ? Math.round((item.count / totalKeywordHits) * 100) : 0;
                
                return (
                  <div key={idx}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, alignItems: 'center' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Tag color={idx < 3 ? 'volcano' : 'default'} style={{ borderRadius: 4, margin: 0, fontWeight: 'bold' }}>
                          NO.{idx + 1}
                        </Tag>
                        <span style={{ fontWeight: 600, color: '#333' }}>“{item.keyword}”</span>
                      </span>
                      <span style={{ color: '#888', fontSize: 12 }}>
                        {item.count} 次 ({percent}%)
                      </span>
                    </div>
                    <Progress 
                      percent={percent} 
                      showInfo={false} 
                      strokeColor={{
                        '0%': idx < 3 ? '#ff4d4f' : '#1890ff',
                        '100%': idx < 3 ? '#fa8c16' : '#87e8de',
                      }}
                      strokeWidth={6}
                      style={{ margin: 0 }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </Col>

      {/* Right Column: Hot Standards */}
      <Col xs={24} md={12}>
        <Card 
          title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><BookOutlined /> 最受关注企业标准 Top 5</span>}
          style={{ height: '100%', borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
          bodyStyle={{ padding: 24 }}
        >
          {hotStandards.length === 0 ? (
            <Empty description="暂无企标被阅览或下载记录" style={{ padding: '60px 0' }} />
          ) : (
            <List
              itemLayout="horizontal"
              dataSource={hotStandards}
              renderItem={(item, idx) => (
                <List.Item 
                  style={{ padding: '12px 0', borderBottom: idx === hotStandards.length - 1 ? 'none' : '1px solid #f0f0f0' }}
                  extra={
                    <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                      <span style={{ fontSize: 14, fontWeight: 'bold', color: '#ff4d4f' }}>
                        <FireOutlined /> {item.count}
                      </span>
                      <span style={{ fontSize: 11, color: '#999' }}>关注度热度值</span>
                    </div>
                  }
                >
                  <List.Item.Meta
                    avatar={
                      <div style={{ 
                        width: 32, 
                        height: 32, 
                        borderRadius: 8, 
                        backgroundColor: idx === 0 ? '#fff2e8' : idx === 1 ? '#f9f0ff' : '#f0f5ff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 'bold',
                        color: idx === 0 ? '#fa541c' : idx === 1 ? '#722ed1' : '#1890ff',
                        fontSize: 14
                      }}>
                        {idx + 1}
                      </div>
                    }
                    title={
                      <span style={{ 
                        fontWeight: 600, 
                        color: '#333',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: 'inline-block',
                        maxWidth: '280px'
                      }}>
                        {item.title}
                      </span>
                    }
                    description={
                      <span style={{ fontSize: 12, color: '#888' }}>
                        标准ID: {item.id} · 被预览与下载次数
                      </span>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Card>
      </Col>
    </Row>
  );
};

export default KeywordsAndStandards;
