import React, { useState, useRef } from 'react';
import { List, Card, Typography, Tag, Space, Button, Empty, Pagination, Modal, Progress, message, Checkbox } from 'antd';
import { EnvironmentOutlined, BankOutlined, FileTextOutlined, CloudDownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import LbsSearchBar from './components/LbsSearchBar';
import StandardDrawer from './components/StandardDrawer';
import { useSearchData } from '@/hooks/useSearchData';
import type { Company, CompanySearchParams } from '@/types';
import apiClient from '@/api/client';

const { Text, Title } = Typography;

const CompanySearchPage: React.FC = () => {
  const [params, setParams] = useState<CompanySearchParams>({ page: 1 });
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<number[]>([]);

  // 打包下载相关状态
  const [packModalVisible, setPackModalVisible] = useState(false);
  const [packProgress, setPackProgress] = useState(0);
  const [packStatusText, setPackStatusText] = useState('');
  const [packError, setPackError] = useState<string | null>(null);
  const pollIntervalRef = useRef<any>(null);

  const { useCompanySearch } = useSearchData();
  const { data: result, isLoading, isFetching } = useCompanySearch(params);

  const handleSearch = (values: CompanySearchParams) => {
    setParams({ ...values, page: 1 });
  };

  const openStandards = (company: Company) => {
    setSelectedCompany(company);
    setDrawerVisible(true);
  };

  const handleSelectCompany = (companyId: number, checked: boolean) => {
    if (checked) {
      setSelectedCompanyIds((prev) => [...prev, companyId]);
    } else {
      setSelectedCompanyIds((prev) => prev.filter((id) => id !== companyId));
    }
  };

  const handlePackSelectedCompanies = async () => {
    if (selectedCompanyIds.length === 0) return;
    setPackError(null);
    setPackProgress(5);
    setPackStatusText('正在向云端提交打包请求...');
    setPackModalVisible(true);

    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', {
        mode: 'selected_companies',
        company_ids: selectedCompanyIds,
      });
      const { token, count } = data;
      setPackProgress(20);
      setPackStatusText(`已成功锁定所选企业名下的企标（共计 ${count} 个），开始在云端打包...`);

      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const res = await apiClient.get<{ status: string; download_url?: string; error?: string }>(
            `/client/standards/pack/${token}/status/`
          );

          if (res.data.status === 'running') {
            setPackProgress(60);
            setPackStatusText('云端正在高速压缩并生成 ZIP 归档中，请稍候...');
          } else if (res.data.status === 'done' && res.data.download_url) {
            setPackProgress(100);
            setPackStatusText('云端打包完成！正在唤起本地安全下载通道...');
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

            const downloadUrl = res.data.download_url;
            window.open(downloadUrl, '_blank');

            setTimeout(() => {
              setPackModalVisible(false);
              message.success('所选企业的企标文件打包下载成功！');
              setSelectedCompanyIds([]);
            }, 1200);
          } else if (res.data.status === 'failed') {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setPackError(res.data.error || '打包失败，请稍后重试');
          }
        } catch (err) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setPackError('轮询状态异常，请检查网络连接');
        }
      }, 1500);

    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      setPackProgress(0);
      setPackError(errMsg);
    }
  };

  const handleCancelPack = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    setPackModalVisible(false);
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 32 }}>
        <Title level={2}>企业标准资源检索</Title>
        <Text type="secondary">支持全国企业标准化数据多维度实时检索与企业标准资产展示。</Text>
      </div>

      <LbsSearchBar onSearch={handleSearch} loading={isFetching} />

      {result && (
        <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <Text style={{ fontSize: 15 }}>
            共找到 <Text strong style={{ fontSize: 16, color: '#1890ff' }}>{result.count}</Text> 家符合条件的企业
          </Text>
        </div>
      )}

      <List
        grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 2, xl: 3, xxl: 3 }}
        dataSource={result?.results || []}
        loading={isLoading}
        locale={{ emptyText: <Empty description="暂无符合条件的企业记录" /> }}
        renderItem={(item: Company) => (
          <List.Item>
            <Card 
              hoverable 
              style={{ borderRadius: 12, border: '1px solid #f0f0f0' }}
              bodyStyle={{ padding: 20 }}
              actions={[
                <Button 
                  type="link" 
                  icon={<FileTextOutlined />} 
                  onClick={() => openStandards(item)}
                  style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}
                >
                  查看标准资产 ({item.standards_count || 0})
                </Button>
              ]}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <Space>
                  <Checkbox 
                    checked={selectedCompanyIds.includes(item.id)}
                    onChange={(e) => handleSelectCompany(item.id, e.target.checked)}
                  />
                  <Tag color={item.status === 'active' ? 'blue' : 'default'} style={{ margin: 0 }}>
                    {item.status === 'active' ? '正常运行' : '停业/异常'}
                  </Tag>
                </Space>
                {item.distance_km !== null && (
                  <Text type="success" strong>
                    <EnvironmentOutlined /> {item.distance_km} km
                  </Text>
                )}
              </div>
              
              <Title level={5} ellipsis={{ tooltip: item.name }} style={{ marginTop: 0, marginBottom: 8 }}>
                <BankOutlined /> {item.name}
              </Title>
              
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Text type="secondary" style={{ fontSize: 13 }}>信用代码: {item.credit_code}</Text>
                <Text type="secondary" style={{ fontSize: 13 }}>法人: {item.legal_person}</Text>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary"><EnvironmentOutlined /> {item.province_name} {item.city_name} {item.district_name}</Text>
                </div>
              </Space>
            </Card>
          </List.Item>
        )}
      />

      {result && result.count > 9 && (
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
          <Pagination
            current={params.page || 1}
            pageSize={9}
            total={result.count}
            onChange={(newPage) => setParams({ ...params, page: newPage })}
            showSizeChanger={false}
            style={{
              background: '#fff',
              padding: '8px 24px',
              borderRadius: 30,
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
              border: '1px solid #f0f0f0'
            }}
          />
        </div>
      )}

      <StandardDrawer 
        company={selectedCompany} 
        open={drawerVisible} 
        onClose={() => setDrawerVisible(false)} 
      />

      {selectedCompanyIds.length > 0 && (
        <div style={{
          position: 'fixed',
          bottom: 24,
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(0, 151, 167, 0.25)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
          borderRadius: 50,
          padding: '12px 32px',
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          zIndex: 1000,
          transition: 'all 0.3s ease'
        }}>
          <Text style={{ fontSize: 15, fontWeight: 500 }}>
            已选 <Text strong style={{ color: '#13c2c2', fontSize: 16 }}>{selectedCompanyIds.length}</Text> 家企业
          </Text>
          <Space>
            <Button 
              onClick={() => setSelectedCompanyIds([])}
              style={{ borderRadius: 20 }}
            >
              取消选择
            </Button>
            <Button
              type="primary"
              icon={<CloudDownloadOutlined />}
              onClick={handlePackSelectedCompanies}
              style={{
                borderRadius: 20,
                background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)',
                borderColor: '#13c2c2',
                fontWeight: 'bold',
                boxShadow: '0 4px 10px rgba(0, 151, 167, 0.15)'
              }}
            >
              打包下载所选企业企标
            </Button>
          </Space>
        </div>
      )}

      {/* 异步打包状态进度 Modal（Glassmorphism 现代质感） */}
      <Modal
        title={
          <Space>
            <CloudDownloadOutlined style={{ color: '#13c2c2', fontSize: 18 }} />
            <span style={{ fontWeight: 'bold' }}>云端企标批量打包系统</span>
          </Space>
        }
        open={packModalVisible}
        onCancel={handleCancelPack}
        footer={[
          <Button key="cancel" onClick={handleCancelPack} style={{ borderRadius: 6 }}>
            {packError ? '关闭' : '取消打包'}
          </Button>
        ]}
        centered
        width={420}
        bodyStyle={{ padding: '24px 16px' }}
      >
        {packError ? (
          <div style={{ textAlign: 'center' }}>
            <Progress type="circle" percent={packProgress} status="exception" width={80} />
            <div style={{ marginTop: 16, color: '#ff4d4f', fontWeight: 'bold', fontSize: 14 }}>
              打包失败
            </div>
            <div style={{ marginTop: 8, color: '#666', fontSize: 13 }}>
              {packError}
            </div>
          </div>
        ) : (
          <div style={{ textAlign: 'center' }}>
            <Progress
              type="circle"
              percent={packProgress}
              strokeColor={{
                '0%': '#13c2c2',
                '100%': '#00bcd4',
              }}
              width={80}
              status="active"
            />
            <div style={{ marginTop: 16, color: '#333', fontWeight: 500, fontSize: 14 }}>
              {packProgress === 100 ? '打包就绪！' : '正在全力打包中...'}
            </div>
            <div style={{ marginTop: 8, color: '#8c8c8c', fontSize: 12, lineHeight: '1.6' }}>
              {packStatusText}
            </div>
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, color: '#bfbfbf', fontSize: 11 }}>
              <InfoCircleOutlined />
              <span>本系统由 Celery 高速异步通道强力驱动</span>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default CompanySearchPage;
