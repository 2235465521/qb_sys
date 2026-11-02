import React, { useState } from 'react';
import { Button, Pagination, message, Space } from 'antd';
import { CloudDownloadOutlined, FileExcelOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import StandardsTable from './components/StandardsTable';
import InlineDownloadBar from './components/InlineDownloadBar';
import DownloadEstimateModal from './components/DownloadEstimateModal';
import ClientExportModal from './components/ClientExportModal';
import { useClientStandardSearch } from '@/hooks/useClientStandardSearch';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const SearchStandardsPage: React.FC = () => {
  const [params, setParams] = useState<any>({
    page: 1,
    keyword: '',
    search_mode: 'title',
    exact_match: false,
    parse_status: 'all',
    province_id: undefined,
    city_id: undefined,
    district_id: undefined
  });

  // 容量估算及下载配置弹窗状态
  const [estimateModalVisible, setEstimateModalVisible] = useState(false);

  // 企标目录 Excel 导出配置弹窗状态
  const [clientExportModalVisible, setClientExportModalVisible] = useState(false);

  // 选中的标准行ID
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  const { dispatchTask } = useTaskContext();

  const { data, isLoading, isFetching } = useClientStandardSearch(params);

  const handleSearch = (searchParams: any) => {
    setParams({
      ...searchParams,
      page: 1
    });
    setSelectedRowKeys([]); // 搜索条件改变清空勾选
  };

  const handlePageChange = (newPage: number) => {
    setParams({
      ...params,
      page: newPage,
    });
    // 翻页不清空勾选，以支持跨页勾选
  };

  const handleTableChange = (_pagination: any, _filters: any, sorter: any) => {
    let ordering = undefined;
    if (sorter && sorter.order) {
      ordering = sorter.order === 'descend' ? `-${sorter.field}` : sorter.field;
    }
    setParams({
      ...params,
      page: 1, // 排序发生变化时回到第一页
      ordering
    });
  };

  // 批量下载已选标准
  const handleBatchDownload = async () => {
    if (selectedRowKeys.length === 0) return;
    
    try {
      const payload = {
        standard_ids: selectedRowKeys.map(k => Number(k))
      };
      const { data: response } = await apiClient.post<{ token: string; count: number }>('/client/standards/pack/', payload);
      const { token, count } = response;
      
      message.success(`已锁定 ${count} 个选定标准，打包任务已提交至后台处理，您可继续浏览其他页面...`);
      dispatchTask(token, '批量下载已选标准', false, '/client/standards/pack/', payload);
      setSelectedRowKeys([]); // 清空选择
    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      message.error(errMsg);
    }
  };

  // 触发按照容量/预估条件包或导出的动作
  const handleEstimateDownload = async (mode: 'zip' | 'excel') => {
    setEstimateModalVisible(false);

    if (mode === 'excel') {
      // 统一打开高级目录导出弹窗
      setClientExportModalVisible(true);
    } else {
      // mode === 'zip'
      try {
        const { page, ...packParams } = params;
        const { data: response } = await apiClient.post<{ token: string; count: number }>('/client/standards/pack/', packParams);
        const { token, count } = response;
        
        message.success(`已锁定符合筛选条件的 ${count} 个企标，打包任务已提交至后台处理，您可继续浏览其他页面...`);
        dispatchTask(token, '按筛选条件批量打包企标', false, '/client/standards/pack/', packParams);
      } catch (err: any) {
        const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
        message.error(errMsg);
      }
    }
  };

  return (
    <div className="search-standards-page" style={{ padding: '4px' }}>
      <SearchForm
        onSearch={handleSearch}
        loading={isFetching}
      />

      {/* 玻璃浮雕质感的操作工具栏 */}
      <div 
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(8px)',
          border: '1px solid #f1f5f9',
          boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)',
          padding: '16px 24px',
          borderRadius: 16,
          marginBottom: 16,
          transition: 'all 0.3s ease'
        }}
      >
        <div style={{ fontSize: 14, color: '#475569', fontWeight: 500 }}>
          当前条件共检索到 <span style={{ fontSize: 16, fontWeight: 'bold', color: '#0d9488' }}>{data?.count || 0}</span> 条企业标准
        </div>

        {/* 内联操作栏：导出目录 Excel + 清单匹配下载 + 抽样策略/数量/打包 */}
        <InlineDownloadBar
          totalCount={data?.count ?? 0}
          filters={params}
          onOpenExportModal={() => setClientExportModalVisible(true)}
        />
      </div>

      {selectedRowKeys.length > 0 && (
        <div 
          style={{ 
            marginBottom: 16, 
            background: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)', 
            border: '1px solid #91d5ff', 
            padding: '12px 24px', 
            borderRadius: 12, 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            boxShadow: '0 4px 15px rgba(24,144,255,0.05)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: '#0050b3' }}>
              已选择 <span style={{ fontSize: 16, fontWeight: 'bold', color: '#1890ff' }}>{selectedRowKeys.length}</span> 个企业标准
            </span>
            <Button type="link" size="small" onClick={() => setSelectedRowKeys([])} style={{ padding: 0 }}>
              取消选择
            </Button>
          </div>
          <Space>
            <Button
              icon={<FileExcelOutlined />}
              onClick={() => setClientExportModalVisible(true)}
              style={{ 
                borderRadius: 8,
                borderColor: '#0d9488',
                color: '#0f766e',
                background: '#fff',
                fontWeight: 500
              }}
            >
              导出已选目录 (Excel)
            </Button>
            <Button
              type="primary"
              icon={<CloudDownloadOutlined />}
              onClick={handleBatchDownload}
              style={{ 
                borderRadius: 8,
                background: 'linear-gradient(135deg, #1890ff 0%, #0050b3 100%)',
                borderColor: '#1890ff'
              }}
            >
              批量下载已选标准
            </Button>
          </Space>
        </div>
      )}

      <StandardsTable
        data={data?.results || []}
        loading={isLoading}
        selectedRowKeys={selectedRowKeys}
        onSelectionChange={setSelectedRowKeys}
        keyword={params.keyword}
        searchMode={params.search_mode}
        onChange={handleTableChange}
      />

      {data && data.count > 0 && (
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
          <Pagination
            current={params.page}
            pageSize={10}
            total={data.count}
            onChange={handlePageChange}
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

      {/* 预估下载弹窗（历史兼容保留） */}
      <DownloadEstimateModal
        open={estimateModalVisible}
        onCancel={() => setEstimateModalVisible(false)}
        onDownload={handleEstimateDownload}
        searchParams={params}
      />

      {/* 客户端企标目录 Excel 导出轻量配置弹窗 */}
      <ClientExportModal
        open={clientExportModalVisible}
        onCancel={() => setClientExportModalVisible(false)}
        selectedIds={selectedRowKeys}
        currentFilters={params}
        totalFilteredCount={data?.count || 0}
      />
    </div>
  );
};

export default SearchStandardsPage;
