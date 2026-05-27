import React, { useState } from 'react';
import { List, Card, Typography, Tag, Space, Button, Empty, Pagination, message, Checkbox } from 'antd';
import { EnvironmentOutlined, BankOutlined, FileTextOutlined, CloudDownloadOutlined } from '@ant-design/icons';
import LbsSearchBar from './components/LbsSearchBar';
import StandardDrawer from './components/StandardDrawer';
import { useSearchData } from '@/hooks/useSearchData';
import type { Company, CompanySearchParams } from '@/types';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const { Text, Title } = Typography;

const CompanySearchPage: React.FC = () => {
  const [params, setParams] = useState<CompanySearchParams>({ page: 1 });
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<number[]>([]);

  const { dispatchTask } = useTaskContext();

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

    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', {
        mode: 'selected_companies',
        company_ids: selectedCompanyIds,
      });
      const { token, count } = data;
      
      message.success(`已锁定所选企业名下的企标（共计 ${count} 个），打包任务已提交至后台处理...`);
      dispatchTask(token, '所选企业企标下载');
      setSelectedCompanyIds([]);

    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      message.error(errMsg);
    }
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
            showQuickJumper
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

      {/* Modal is removed and managed by TaskContext */}
    </div>
  );
};

export default CompanySearchPage;
