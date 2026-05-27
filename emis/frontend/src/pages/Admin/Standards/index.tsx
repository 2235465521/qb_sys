import React, { useState } from 'react';
import { Button, Space, message } from 'antd';
import { ImportOutlined, FileTextOutlined, ReloadOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import DataTable from './components/DataTable';
import ImportModal from './components/ImportModal';
import EditModal from './components/EditModal';
import { useStandardData } from '@/hooks/useStandardData';
import type { StandardSearchParams } from '@/hooks/useStandardData';
import type { Standard } from '@/types';
import apiClient from '@/api/client';

const StandardsManagerPage: React.FC = () => {
  const [params, setParams] = useState<StandardSearchParams>({ page: 1 });
  const [importVisible, setImportVisible] = useState(false);
  const [editVisible, setEditVisible] = useState(false);
  const [editingStandard, setEditingStandard] = useState<Standard | null>(null);
  const [scanning, setScanning] = useState(false);

  const { standardQuery, saveMutation, deleteMutation } = useStandardData(params);

  const handleSearch = (values: StandardSearchParams) => {
    setParams({ ...params, ...values, page: 1 });
  };

  const handleTableChange = (pagination: any) => {
    setParams({
      ...params,
      page: pagination.current,
    });
  };

  const handleEdit = (record: Standard) => {
    setEditingStandard(record);
    setEditVisible(true);
  };

  const handleSave = (values: Partial<Standard>) => {
    saveMutation.mutate(values, {
      onSuccess: () => {
        setEditVisible(false);
        setEditingStandard(null);
      }
    });
  };

  const handleScanSync = async () => {
    setScanning(true);
    try {
      const { data } = await apiClient.post('/client/standards/scan-pdf-sync/');
      message.success(data.message || '扫盘对齐成功！');
      standardQuery.refetch();
    } catch (err: any) {
      const errMsg = err?.response?.data?.error || '扫盘失败，请重试';
      message.error(errMsg);
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="standards-manager-page" style={{ padding: '4px' }}>
      <div 
        style={{ 
          marginBottom: 20, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 2px 10px rgba(0,0,0,0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#1677ff', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <FileTextOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#1a1a1a', fontWeight: 'bold' }}>企业标准管理</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#666' }}>集中展示与维系全国企标资产，支持空间定位对齐及极速批量入库。</p>
          </div>
        </div>
        <Space>
          <Button 
            icon={<ReloadOutlined />} 
            onClick={handleScanSync}
            loading={scanning}
            style={{ borderRadius: 6, fontWeight: 500 }}
          >
            一键扫盘匹配 PDF
          </Button>
          <Button 
            type="primary" 
            icon={<ImportOutlined />} 
            onClick={() => setImportVisible(true)}
            style={{ borderRadius: 6, fontWeight: 500 }}
          >
            一键导入企标
          </Button>
        </Space>
      </div>

      <SearchForm
        onSearch={handleSearch}
        loading={standardQuery.isFetching}
      />

      <DataTable
        data={standardQuery.data?.results || []}
        loading={standardQuery.isLoading}
        pagination={{ showQuickJumper: true,
          current: params.page,
          pageSize: 20,
          total: standardQuery.data?.count || 0,
        }}
        onEdit={handleEdit}
        onDelete={(id) => deleteMutation.mutate(id)}
        onChange={handleTableChange}
      />

      <ImportModal
        open={importVisible}
        onCancel={() => setImportVisible(false)}
        onSuccess={() => {
          standardQuery.refetch();
        }}
      />

      <EditModal
        open={editVisible}
        editingStandard={editingStandard}
        onCancel={() => {
          setEditVisible(false);
          setEditingStandard(null);
        }}
        onSave={handleSave}
        confirmLoading={saveMutation.isPending}
      />
    </div>
  );
};

export default StandardsManagerPage;
