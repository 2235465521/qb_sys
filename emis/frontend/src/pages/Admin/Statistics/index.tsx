import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Spin, Typography, Row, Col, Button } from 'antd';
import { ReloadOutlined, HistoryOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

import StatsCards from './components/StatsCards';
import TrendLineChart from './components/TrendLineChart';
import UserBarChart from './components/UserBarChart';
import TimeDistributionChart from './components/TimeDistributionChart';
import KeywordsAndStandards from './components/KeywordsAndStandards';
import LogsTable from './components/LogsTable';
import type { LogEntry } from './components/LogsTable';

const { Title, Paragraph } = Typography;

export interface StatisticsSummary {
  total_hits: number;
  today_hits: number;
  active_users_today: number;
  active_users_week: number;
  total_users: number;
  dau_rate: number;
  wau_rate: number;
  total_warnings: number;
}

export interface ChartsData {
  trend: { date: string; count: number }[];
  top_users: { username: string; real_name: string; count: number }[];
  hourly_distribution: { hour: string; count: number }[];
  hot_keywords: { keyword: string; count: number }[];
  hot_standards: { id: string; title: string; count: number }[];
}

export interface LogsResponse {
  results: LogEntry[];
  count: number;
}

const StatisticsPage: React.FC = () => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [filters, setFilters] = useState<any>({});

  // 1. 获取基础指标统计
  const { 
    data: summary, 
    isLoading: isSummaryLoading, 
    refetch: refetchSummary 
  } = useQuery<StatisticsSummary>({
    queryKey: ['adminStatisticsSummary'],
    queryFn: async () => {
      const { data } = await apiClient.get<StatisticsSummary>('/admin/statistics/summary/');
      return data;
    }
  });

  // 2. 获取统计图表数据
  const { 
    data: charts, 
    isLoading: isChartsLoading, 
    refetch: refetchCharts 
  } = useQuery<ChartsData>({
    queryKey: ['adminStatisticsCharts'],
    queryFn: async () => {
      const { data } = await apiClient.get<ChartsData>('/admin/statistics/charts/');
      return data;
    }
  });

  // 3. 获取明细审计日志
  const { 
    data: logsData, 
    isLoading: isLogsLoading, 
    refetch: refetchLogs 
  } = useQuery<LogsResponse>({
    queryKey: ['adminStatisticsLogs', page, pageSize, filters],
    queryFn: async () => {
      const params: any = {
        page,
        page_size: pageSize,
        ...filters
      };
      const { data } = await apiClient.get<LogsResponse>('/admin/statistics/logs/', { params });
      return data;
    }
  });

  // 手动一键刷新
  const handleRefreshAll = () => {
    refetchSummary();
    refetchCharts();
    refetchLogs();
  };

  // 过滤条件提交
  const handleFilterSubmit = (formValues: any) => {
    const formattedFilters: any = {};
    if (formValues.keyword) formattedFilters.keyword = formValues.keyword;
    if (formValues.action) formattedFilters.action = formValues.action;
    if (formValues.is_warning) formattedFilters.is_warning = formValues.is_warning;
    
    if (formValues.dates && formValues.dates.length === 2) {
      formattedFilters.start_date = formValues.dates[0].format('YYYY-MM-DD');
      formattedFilters.end_date = formValues.dates[1].format('YYYY-MM-DD');
    }
    
    setFilters(formattedFilters);
    setPage(1); // 重置到第一页
  };

  // 重置过滤
  const handleReset = () => {
    setFilters({});
    setPage(1);
  };

  const handleTableChange = (newPage: number, newSize: number) => {
    setPage(newPage);
    setPageSize(newSize);
  };

  const isGlobalLoading = isSummaryLoading || isChartsLoading;

  if (isGlobalLoading || !summary || !charts) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '70vh', flexDirection: 'column', gap: 16 }}>
        <Spin size="large" />
        <span style={{ color: '#999' }}>正在计算和加载用户活跃及使用日志看板...</span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 0 24px 0' }}>
      
      {/* Page Header Header */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center', 
        background: '#fff', 
        padding: 24, 
        borderRadius: 16, 
        border: '1px solid #f0f0f0', 
        boxShadow: '0 4px 20px rgba(0,0,0,0.02)' 
      }}>
        <div>
          <Title level={3} style={{ margin: 0, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 10 }}>
            <HistoryOutlined style={{ color: '#1890ff' }} /> 用户活跃情况与审计监控
          </Title>
          <Paragraph type="secondary" style={{ margin: '8px 0 0 0' }}>
            此处统计用户在平台的日常请求情况、活跃曲线率、高频检索热词词条，并对高频下载PDF等危险抓取行为进行安全拦截预警。
          </Paragraph>
        </div>
        <Button 
          type="primary" 
          icon={<ReloadOutlined />} 
          onClick={handleRefreshAll}
          style={{ borderRadius: 8, height: 40 }}
        >
          实时数据刷新
        </Button>
      </div>

      {/* KPI Cards */}
      <StatsCards 
        totalHits={summary.total_hits}
        todayHits={summary.today_hits}
        activeUsersToday={summary.active_users_today}
        activeUsersWeek={summary.active_users_week}
        dauRate={summary.dau_rate}
        wauRate={summary.wau_rate}
        totalWarnings={summary.total_warnings}
      />

      {/* Grid: Trend Line and User Activity Bar */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <TrendLineChart trend={charts.trend} />
        </Col>
        <Col xs={24} lg={12}>
          <UserBarChart topUsers={charts.top_users} />
        </Col>
      </Row>

      {/* Grid: 24-Hour Time Distribution */}
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <TimeDistributionChart hourlyDistribution={charts.hourly_distribution} />
        </Col>
      </Row>

      {/* Keywords and Hot Standards Row */}
      <KeywordsAndStandards 
        hotKeywords={charts.hot_keywords}
        hotStandards={charts.hot_standards}
      />

      {/* Main Audit Log Table */}
      <LogsTable 
        logs={logsData?.results || []}
        total={logsData?.count || 0}
        current={page}
        pageSize={pageSize}
        isLoading={isLogsLoading}
        onTableChange={handleTableChange}
        onFilterSubmit={handleFilterSubmit}
        onReset={handleReset}
      />

    </div>
  );
};

export default StatisticsPage;
