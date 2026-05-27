import React, { useState, useRef } from 'react';
import { Space, Button, Pagination, Modal, Progress, message, Typography } from 'antd';
import { FileTextOutlined, CloudDownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import StandardsTable from './components/StandardsTable';
import CustomPackModal from './components/CustomPackModal';
import { useClientStandardSearch } from '@/hooks/useClientStandardSearch';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const { Text } = Typography;

const SearchStandardsPage: React.FC = () => {
  const [params, setParams] = useState({ page: 1, keyword: '' });

  // 自定义打包弹窗状态
  const [customPackVisible, setCustomPackVisible] = useState(false);

  const { dispatchTask } = useTaskContext();

  const { data, isLoading, isFetching } = useClientStandardSearch(params);

  const handleSearch = (keyword: string) => {
    setParams({ keyword, page: 1 });
  };

  const handlePageChange = (newPage: number) => {
    setParams({
      ...params,
      page: newPage,
    });
  };

  // 触发 100 个随机企标批量打包下载
  const handleRandomPack100 = async () => {
    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', { mode: 'standards' });
      const { token, count } = data;
      
      message.success(`已锁定 ${count} 个企标，打包任务已提交至后台处理，您可继续浏览其他页面...`);
      dispatchTask(token, '随机下载100个企标');

    } catch (err: any) {
      const errMsg = err.response?.data?.error || '提交请求失败，没有找到可供下载的企标 PDF 文件';
      message.error(errMsg);
    }
  };

  const handleCancelPack = () => {
    // Legacy modal function
  };

  const handleCustomPack = async (packParams: { province_ids: number[], city_ids: number[], parse_target: string }) => {
    setCustomPackVisible(false);

    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', { 
        mode: 'custom_filter',
        ...packParams
      });
      const { token, count } = data;
      
      message.success(`已锁定 ${count} 个企标，打包任务已提交至后台处理，您可继续浏览其他页面...`);
      dispatchTask(token, '自定义选择下载');

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

        <div style={{ display: 'flex', gap: 12 }}>
          <Button
            onClick={() => setCustomPackVisible(true)}
            style={{
              borderRadius: 8,
              height: 40,
              fontWeight: 'bold',
              color: '#00838f',
              borderColor: '#00838f',
              background: 'transparent'
            }}
          >
            自定义选择下载
          </Button>
          <Button
            type="primary"
            icon={<CloudDownloadOutlined />}
            onClick={handleRandomPack100}
            style={{
              borderRadius: 8,
              background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
              borderColor: '#00acc1',
              fontWeight: 'bold',
              height: 40,
              boxShadow: '0 4px 12px rgba(0, 131, 143, 0.2)'
            }}
          >
            一键随机下载 100 个企标
          </Button>
        </div>
      </div>

      <SearchForm
        onSearch={handleSearch}
        loading={isFetching}
      />

      <StandardsTable
        data={data?.results || []}
        loading={isLoading}
      />

      {data && data.count > 0 && (
        <div style={{ marginTop: 24, display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 12, marginBottom: 24 }}>
          <Text type="secondary">共计 {data.count} 条企业标准</Text>
          <Pagination
            current={params.page}
            pageSize={10}
            total={data.count}
            onChange={handlePageChange}
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

      {/* Modal is removed and managed by TaskContext */}

      <CustomPackModal
        open={customPackVisible}
        onCancel={() => setCustomPackVisible(false)}
        onSubmit={handleCustomPack}
      />
    </div>
  );
};

export default SearchStandardsPage;
