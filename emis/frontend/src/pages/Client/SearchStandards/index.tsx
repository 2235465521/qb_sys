import React, { useState } from 'react';
import { Button, Pagination, message } from 'antd';
import { FileTextOutlined, CloudDownloadOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import StandardsTable from './components/StandardsTable';
import CustomPackModal from './components/CustomPackModal';
import DownloadEstimateModal from './components/DownloadEstimateModal';
import { useClientStandardSearch } from '@/hooks/useClientStandardSearch';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const SearchStandardsPage: React.FC = () => {
  const [params, setParams] = useState<any>({
    page: 1,
    keyword: '',
    search_mode: 'title',
    parse_status: 'all',
    province_id: undefined,
    city_id: undefined,
    district_id: undefined
  });

  // 自定义打包弹窗状态
  const [customPackVisible, setCustomPackVisible] = useState(false);

  // 容量估算及下载配置弹窗状态
  const [estimateModalVisible, setEstimateModalVisible] = useState(false);

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
      const hide = message.loading('正在生成企业标准目录 Excel，请稍候...', 0);
      try {
        const { data: fileBlob, headers } = await apiClient.get('/client/standards/export/', {
          params,
          responseType: 'blob'
        });
        hide();

        const blob = new Blob([fileBlob], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;

        const contentDisposition = headers['content-disposition'];
        let filename = '企业标准目录.xlsx';
        if (contentDisposition) {
          const match = contentDisposition.match(/filename\*=UTF-8''(.+)$/);
          if (match && match[1]) {
            filename = decodeURIComponent(match[1]);
          } else {
            const match2 = contentDisposition.match(/filename=(.+)$/);
            if (match2 && match2[1]) {
              filename = decodeURIComponent(match2[1]);
            }
          }
        }

        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        message.success('Excel 目录文件导出成功！');
      } catch (err: any) {
        hide();
        message.error('导出 Excel 失败，请检查网络或稍后重试');
        console.error(err);
      }
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

  // 触发 100 个随机企标批量打包下载
  const handleRandomPack100 = async () => {
    try {
      const payload = { mode: 'standards' };
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', payload);
      const { token, count } = data;
      
      message.success(`已锁定 ${count} 个企标，打包任务已提交至后台处理，您可继续浏览其他页面...`);
      dispatchTask(token, '随机下载100个企标', false, '/client/standards/random-pack/', payload);

    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      message.error(errMsg);
    }
  };

  const handleCustomPack = async (packParams: { province_ids: number[], city_ids: number[], parse_target: string }) => {
    setCustomPackVisible(false);

    try {
      const payload = { 
        mode: 'custom_filter',
        ...packParams
      };
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', payload);
      const { token, count } = data;
      
      message.success(`已锁定 ${count} 个企标，打包任务已提交至后台处理，您可继续浏览其他页面...`);
      dispatchTask(token, '自定义选择下载', false, '/client/standards/random-pack/', payload);

    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      message.error(errMsg);
    }
  };

  return (
    <div className="search-standards-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
      <div 
        style={{ 
          marginBottom: 20, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 4px 15px rgba(0,0,0,0.03)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#00bcd4', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <FileTextOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#006064', fontWeight: 'bold' }}>检索企业标准</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#00838f' }}>
              支持根据标准编号或名称进行快速模糊检索，与管理后台标准资产完全映射，并可直接下载关联的标准 PDF 附件。
            </p>
          </div>
        </div>
      </div>

      <SearchForm
        onSearch={handleSearch}
        loading={isFetching}
        onCustomPack={() => setCustomPackVisible(true)}
        onRandomPack100={handleRandomPack100}
      />

      {/* 玻璃浮雕质感的操作工具栏 */}
      <div 
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'rgba(255, 255, 255, 0.65)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.5)',
          boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.8), 0 4px 16px rgba(0, 0, 0, 0.04)',
          padding: '12px 24px',
          borderRadius: 12,
          marginBottom: 16,
          transition: 'all 0.3s ease'
        }}
      >
        <div style={{ fontSize: 14, color: '#006064', fontWeight: 500 }}>
          当前条件共检索到 <span style={{ fontSize: 16, fontWeight: 'bold', color: '#00acc1' }}>{data?.count || 0}</span> 条企业标准
        </div>
        <Button
          type="primary"
          icon={<CloudDownloadOutlined />}
          onClick={() => setEstimateModalVisible(true)}
          disabled={!data || data.count === 0}
          style={{
            borderRadius: 8,
            background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
            borderColor: '#00acc1',
            fontWeight: 'bold',
            boxShadow: '0 4px 12px rgba(0, 131, 143, 0.2)'
          }}
        >
          批量下载（按当前条件）
        </Button>
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
        </div>
      )}

      <StandardsTable
        data={data?.results || []}
        loading={isLoading}
        selectedRowKeys={selectedRowKeys}
        onSelectionChange={setSelectedRowKeys}
        keyword={params.keyword}
        searchMode={params.search_mode}
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

      <CustomPackModal
        open={customPackVisible}
        onCancel={() => setCustomPackVisible(false)}
        onSubmit={handleCustomPack}
      />

      <DownloadEstimateModal
        open={estimateModalVisible}
        onCancel={() => setEstimateModalVisible(false)}
        onDownload={handleEstimateDownload}
        searchParams={params}
      />
    </div>
  );
};

export default SearchStandardsPage;
