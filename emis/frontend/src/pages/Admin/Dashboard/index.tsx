import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Spin, Typography, Row, Col } from 'antd';
import apiClient from '@/api/client';

import StatsCards from './components/StatsCards';
import TrendChart from './components/TrendChart';
import DistributionCard from './components/DistributionCard';
import QuickActions from './components/QuickActions';

const { Title, Paragraph } = Typography;

export interface DashboardStats {
  total_companies: number;
  active_companies: number;
  total_members: number;
  active_members: number;
  total_standards: number;
  enterprise_standards: number;
  national_standards: number;
  total_sms_tasks: number;
  total_sent_sms: number;
  company_trend: { month: string; count: number }[];
  standard_distribution: { type: string; value: number }[];
}

const DashboardPage: React.FC = () => {
  const { data: stats, isLoading } = useQuery<DashboardStats>({
    queryKey: ['adminDashboardStats'],
    queryFn: async () => {
      const { data } = await apiClient.get<DashboardStats>('/admin/companies/dashboard/stats/');
      return data;
    }
  });

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 6) return '凌晨好，辛苦了！';
    if (hour < 12) return '早上好！';
    if (hour < 14) return '中午好！';
    if (hour < 18) return '下午好！';
    return '晚上好！';
  };

  const currentDate = new Date().toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  });

  if (isLoading || !stats) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '70vh', flexDirection: 'column', gap: 16 }}>
        <Spin size="large" />
        <span style={{ color: '#999' }}>正在加载控制台统计看板数据...</span>
      </div>
    );
  }

  return (
    <div style={{ padding: '0 0 24px 0', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Welcome Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', background: '#fff', padding: 24, borderRadius: 16, border: '1px solid #f0f0f0', boxShadow: '0 4px 20px rgba(0,0,0,0.02)' }}>
        <div>
          <Title level={3} style={{ margin: 0, fontWeight: 'bold' }}>{getGreeting()} 超级管理员</Title>
          <Paragraph type="secondary" style={{ margin: '8px 0 0 0' }}>
            欢迎回来！当前平台运行一切正常。您可以在这里总览企业资质信息、标准库分布、会员系统运行状态以及自动化短信群发任务。
          </Paragraph>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span style={{ color: '#999', fontSize: 13 }}>当前系统时间</span>
          <div style={{ fontSize: 15, fontWeight: 500, color: '#333', marginTop: 4 }}>{currentDate}</div>
        </div>
      </div>

      {/* Top Metrics Cards */}
      <StatsCards 
        totalCompanies={stats.total_companies}
        activeCompanies={stats.active_companies}
        totalMembers={stats.total_members}
        activeMembers={stats.active_members}
        totalStandards={stats.total_standards}
        enterpriseStandards={stats.enterprise_standards}
        nationalStandards={stats.national_standards}
        totalSmsTasks={stats.total_sms_tasks}
        totalSentSms={stats.total_sent_sms}
      />

      {/* Grid of Trends and Distribution */}
      <Row gutter={[24, 24]}>
        <Col xs={24} lg={15}>
          <TrendChart trend={stats.company_trend} />
        </Col>
        <Col xs={24} lg={9}>
          <DistributionCard distribution={stats.standard_distribution} />
        </Col>
      </Row>

      {/* Shortcuts and Server System Monitors */}
      <QuickActions />
    </div>
  );
};

export default DashboardPage;
