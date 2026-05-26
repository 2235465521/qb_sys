import React, { useState, useRef } from 'react';
import { Space, Button, Pagination, Modal, Progress, message, Typography } from 'antd';
import { FileTextOutlined, CloudDownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import StandardsTable from './components/StandardsTable';
import CustomPackModal from './components/CustomPackModal';
import { useClientStandardSearch } from '@/hooks/useClientStandardSearch';
import apiClient from '@/api/client';

const { Text } = Typography;

const SearchStandardsPage: React.FC = () => {
  const [params, setParams] = useState({ page: 1, keyword: '' });

  // 批量下载相关状态
  const [packModalVisible, setPackModalVisible] = useState(false);
  const [packProgress, setPackProgress] = useState(0);
  const [packStatusText, setPackStatusText] = useState('');
  const [packError, setPackError] = useState<string | null>(null);
  const pollIntervalRef = useRef<any>(null);

  // 自定义打包弹窗状态
  const [customPackVisible, setCustomPackVisible] = useState(false);

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
    setPackError(null);
    setPackProgress(5);
    setPackStatusText('正在向云端提交打包请求...');
    setPackModalVisible(true);

    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', { mode: 'standards' });
      const { token, count } = data;
      setPackProgress(25);
      setPackStatusText(`已成功锁定 ${count} 个符合条件（已上传 PDF 附件）的企标，开始云端打包...`);

      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const res = await apiClient.get<{ status: string; download_url?: string; error?: string }>(
            `/client/standards/pack/${token}/status/`
          );

          if (res.data.status === 'running') {
            setPackProgress(65);
            setPackStatusText('云端正在高速压缩并生成 ZIP 归档中，请稍候...');
          } else if (res.data.status === 'done' && res.data.download_url) {
            setPackProgress(100);
            setPackStatusText('云端打包完成！正在唤起本地安全下载通道...');
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

            const downloadUrl = res.data.download_url;
            window.open(downloadUrl, '_blank');

            setTimeout(() => {
              setPackModalVisible(false);
              message.success('成功打包下载 100 个随机企标文件！');
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

  const handleCustomPack = async (packParams: { province_ids: number[], city_ids: number[], parse_target: string }) => {
    setCustomPackVisible(false);
    setPackError(null);
    setPackProgress(5);
    setPackStatusText('正在向云端提交自定义打包请求...');
    setPackModalVisible(true);

    try {
      const { data } = await apiClient.post<{ token: string; count: number }>('/client/standards/random-pack/', { 
        mode: 'custom_filter',
        ...packParams
      });
      const { token, count } = data;
      setPackProgress(25);
      setPackStatusText(`已成功锁定 ${count} 个符合条件的企标，开始云端打包及生成 Excel...`);

      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const res = await apiClient.get<{ status: string; download_url?: string; error?: string }>(
            `/client/standards/pack/${token}/status/`
          );

          if (res.data.status === 'running') {
            setPackProgress(65);
            setPackStatusText('云端正在生成 Excel 并高速压缩 ZIP 归档中，请稍候...');
          } else if (res.data.status === 'done' && res.data.download_url) {
            setPackProgress(100);
            setPackStatusText('云端打包完成！正在唤起本地安全下载通道...');
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

            const downloadUrl = res.data.download_url;
            window.open(downloadUrl, '_blank');

            setTimeout(() => {
              setPackModalVisible(false);
              message.success('成功完成自定义批量打包下载！');
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

      {/* 异步打包状态进度 Modal（Glassmorphism 现代质感） */}
      <Modal
        title={
          <Space>
            <CloudDownloadOutlined style={{ color: '#00acc1', fontSize: 18 }} />
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
                '0%': '#00acc1',
                '100%': '#00838f',
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

      <CustomPackModal
        open={customPackVisible}
        onCancel={() => setCustomPackVisible(false)}
        onSubmit={handleCustomPack}
      />
    </div>
  );
};

export default SearchStandardsPage;
