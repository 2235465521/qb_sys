import React, { useState } from 'react';
import { List, Card, Typography, Tag, Space, Button, Empty, Pagination, message, Checkbox, Modal, Badge, Radio } from 'antd';
import { EnvironmentOutlined, BankOutlined, FileTextOutlined, CloudDownloadOutlined, ShoppingCartOutlined, DeleteOutlined } from '@ant-design/icons';
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
  
  // 跨页已选择企业状态池
  const [selectedEnterprises, setSelectedEnterprises] = useState<Company[]>([]);
  // 购物车弹窗显隐
  const [cartVisible, setCartVisible] = useState(false);
  
  // 导出模式配置弹窗
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportMode, setExportMode] = useState<'selected' | 'filtered'>('filtered');

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

  // 辅助判定当前企业是否勾选
  const isSelected = (companyId: number) => selectedEnterprises.some(c => c.id === companyId);

  // 单个企业选择/取消勾选
  const handleSelectCompany = (company: Company, checked: boolean) => {
    if (checked) {
      if (!isSelected(company.id)) {
        setSelectedEnterprises((prev) => [...prev, company]);
      }
    } else {
      setSelectedEnterprises((prev) => prev.filter((c) => c.id !== company.id));
    }
  };

  const currentPageResults = result?.results || [];
  
  // 判定当前页的所有企业是否都已经勾选
  const isCurrentPageAllSelected = currentPageResults.length > 0 && 
    currentPageResults.every(item => isSelected(item.id));

  // 本页全选勾选改变回调
  const handleSelectAllCurrentPage = (checked: boolean) => {
    if (checked) {
      setSelectedEnterprises(prev => {
        const next = [...prev];
        currentPageResults.forEach(company => {
          if (!next.some(c => c.id === company.id)) {
            next.push(company);
          }
        });
        return next;
      });
    } else {
      const currentPageIds = currentPageResults.map(c => c.id);
      setSelectedEnterprises(prev => prev.filter(c => !currentPageIds.includes(c.id)));
    }
  };

  // 打开打包范围选择弹窗
  const handleOpenExportModal = () => {
    setExportMode(selectedEnterprises.length > 0 ? 'selected' : 'filtered');
    setExportModalVisible(true);
  };

  // 确认并启动打包任务
  const confirmExport = () => {
    setExportModalVisible(false);
    handlePackSelectedCompanies(exportMode);
  };

  // 打包所选企业企标
  const handlePackSelectedCompanies = async (mode: 'selected' | 'filtered') => {
    if (mode === 'selected' && selectedEnterprises.length === 0) return;
    if (mode === 'filtered' && (!result || result.count === 0)) {
      message.warning('当前检索条件下无可打包企业');
      return;
    }

    try {
      const payload: any = {
        export_all: mode === 'filtered'
      };

      if (mode === 'selected') {
        payload.enterprise_ids = selectedEnterprises.map(c => c.id);
      } else {
        const { page, ...filters } = params;
        payload.filters = filters;
      }

      const { data } = await apiClient.post<{ task_id: string }>('/client/standards/pack-enterprises/', payload);
      
      message.success('已成功提交后台打包任务！您可在右上角任务中心查看进度');
      dispatchTask(data.task_id, '企业企标批量下载', true, '/client/standards/pack-enterprises/', payload);
      
      if (mode === 'selected') {
        setSelectedEnterprises([]); // 提交后清空选中
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.error || '分发任务请求失败，请稍后重试';
      message.error(errMsg);
    }
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <LbsSearchBar onSearch={handleSearch} loading={isFetching} />

      {result && (
        <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <Space size={16}>
            <Text style={{ fontSize: 15 }}>
              共找到 <Text strong style={{ fontSize: 16, color: '#1890ff' }}>{result.count}</Text> 家符合条件的企业
            </Text>
            {currentPageResults.length > 0 && (
              <Checkbox
                checked={isCurrentPageAllSelected}
                indeterminate={
                  currentPageResults.some(item => isSelected(item.id)) && !isCurrentPageAllSelected
                }
                onChange={(e) => handleSelectAllCurrentPage(e.target.checked)}
                style={{ fontSize: 14, fontWeight: 500 }}
              >
                本页全选
              </Checkbox>
            )}
          </Space>
          <Space>
            <Button
              type="primary"
              icon={<CloudDownloadOutlined />}
              onClick={handleOpenExportModal}
              style={{
                borderRadius: 16,
                background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)',
                borderColor: '#13c2c2',
                boxShadow: '0 2px 8px rgba(0, 151, 167, 0.15)'
              }}
            >
              打包下载企标 PDF
            </Button>
          </Space>
        </div>
      )}

      <List
        grid={{ gutter: 16, xs: 1, sm: 1, md: 2, lg: 2, xl: 3, xxl: 3 }}
        dataSource={currentPageResults}
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
                    checked={isSelected(item.id)}
                    onChange={(e) => handleSelectCompany(item, e.target.checked)}
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

      {/* 右下角悬浮“已选清单（购物车）”按钮 */}
      {selectedEnterprises.length > 0 && (
        <div style={{
          position: 'fixed',
          bottom: 30,
          right: 30,
          zIndex: 1000,
        }}>
          <Badge count={selectedEnterprises.length} showZero={false} offset={[-8, 8]}>
            <Button
              type="primary"
              shape="circle"
              icon={<ShoppingCartOutlined style={{ fontSize: 20 }} />}
              size="large"
              onClick={() => setCartVisible(true)}
              style={{
                width: 56,
                height: 56,
                background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)',
                borderColor: '#13c2c2',
                boxShadow: '0 4px 16px rgba(0, 151, 167, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            />
          </Badge>
        </div>
      )}

      {/* 已选清单（购物车）弹窗 Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 600 }}>
            <ShoppingCartOutlined style={{ color: '#13c2c2' }} />
            <span>已选企业打包清单 ({selectedEnterprises.length})</span>
          </div>
        }
        open={cartVisible}
        onCancel={() => setCartVisible(false)}
        width={540}
        footer={[
          <Button key="clear" onClick={() => setSelectedEnterprises([])} style={{ borderRadius: 16 }}>
            清空已选
          </Button>,
          <Button key="close" onClick={() => setCartVisible(false)} style={{ borderRadius: 16 }}>
            关闭
          </Button>,
          <Button
            key="download"
            type="primary"
            icon={<CloudDownloadOutlined />}
            onClick={() => {
              setCartVisible(false);
              handleOpenExportModal();
            }}
            disabled={selectedEnterprises.length === 0}
            style={{
              borderRadius: 16,
              background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)',
              borderColor: '#13c2c2',
              boxShadow: '0 4px 10px rgba(0, 151, 167, 0.15)'
            }}
          >
            打包下载 PDF 企标
          </Button>
        ]}
      >
        <div style={{ maxHeight: 350, overflowY: 'auto', paddingRight: 4, marginTop: 12 }}>
          {selectedEnterprises.length === 0 ? (
            <Empty description="已选列表空空如也，请先在页面中勾选企业" style={{ padding: '32px 0' }} />
          ) : (
            <List
              size="small"
              dataSource={selectedEnterprises}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button 
                      type="text" 
                      danger 
                      icon={<DeleteOutlined />} 
                      onClick={() => handleSelectCompany(item, false)}
                    />
                  ]}
                >
                  <List.Item.Meta
                    avatar={<BankOutlined style={{ color: '#8c8c8c', fontSize: 16, marginTop: 4 }} />}
                    title={<span style={{ fontWeight: 500 }}>{item.name}</span>}
                    description={
                      <Space size={8} style={{ fontSize: 11 }}>
                        <span>信用代码: {item.credit_code}</span>
                        <span>•</span>
                        <Tag style={{ fontSize: 10, margin: 0 }}>{item.standards_count || 0} 个企标</Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>
      </Modal>

      {/* 导出模式选择弹窗 */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 600 }}>
            <CloudDownloadOutlined style={{ color: '#1890ff' }} />
            <span>打包导出 PDF 企标范围选择</span>
          </div>
        }
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        width={480}
        footer={[
          <Button key="cancel" onClick={() => setExportModalVisible(false)} style={{ borderRadius: 16 }}>
            取消
          </Button>,
          <Button
            key="submit"
            type="primary"
            onClick={confirmExport}
            style={{
              borderRadius: 16,
              background: 'linear-gradient(135deg, #1890ff 0%, #0050b3 100%)',
              borderColor: '#1890ff'
            }}
          >
            开始打包
          </Button>
        ]}
      >
        <div style={{ padding: '12px 0 12px 0' }}>
          <Text type="secondary" style={{ fontSize: 13, display: 'block', marginBottom: 20 }}>
            请选择您要导出的 PDF 文件打包范围，后端异步打包单次最多支持 200 家企业。
          </Text>
          <Radio.Group 
            value={exportMode} 
            onChange={(e) => setExportMode(e.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: 16, width: '100%' }}
          >
            <Radio 
              value="selected" 
              disabled={selectedEnterprises.length === 0}
              style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: 500, fontSize: 14 }}>
                  模式一：仅打包已勾选的企业 (共 <span style={{ color: '#13c2c2', fontWeight: 'bold' }}>{selectedEnterprises.length}</span> 家)
                </span>
                <span style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
                  仅打包您在购物车或列表中手动勾选的企业文件
                </span>
              </div>
            </Radio>
            <Radio 
              value="filtered"
              style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontWeight: 500, fontSize: 14 }}>
                  模式二：按当前检索条件全选导出 (当前匹配 <span style={{ color: '#1890ff', fontWeight: 'bold' }}>{result?.count || 0}</span> 家)
                </span>
                <span style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
                  按照您当前的地区、关键词等过滤条件打包（上限截取前 200 家企业）
                </span>
              </div>
            </Radio>
          </Radio.Group>
        </div>
      </Modal>

    </div>
  );
};

export default CompanySearchPage;
