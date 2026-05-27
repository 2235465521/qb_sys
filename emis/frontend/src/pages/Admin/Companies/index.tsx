import React, { useState } from 'react';
import { Button, Space, message } from 'antd';
import { PlusOutlined, ExportOutlined, ImportOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import DataTable from './components/DataTable';
import ActionModal from './components/ActionModal';
import ImportModal from './components/ImportModal';
import { useCompanyData } from '@/hooks/useCompanyData';
import type { Company, CompanySearchParams } from '@/types';
import apiClient from '@/api/client';

const CompanyListPage: React.FC = () => {
  const [params, setParams] = useState<CompanySearchParams>({ page: 1 });
  const [modalVisible, setModalVisible] = useState(false);
  const [importVisible, setImportVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Company | null>(null);

  const { companyQuery, saveMutation, deleteMutation } = useCompanyData(params);

  const handleSearch = (values: CompanySearchParams) => {
    setParams({ ...params, ...values, page: 1 });
  };

  const handleReset = () => {
    setParams({ page: 1 });
  };

  const handleTableChange = (pagination: any) => {
    setParams({
      ...params,
      page: pagination.current,
    });
  };

  const handleAdd = () => {
    setEditingRecord(null);
    setModalVisible(true);
  };

  const handleEdit = (record: Company) => {
    setEditingRecord(record);
    setModalVisible(true);
  };

  const handleExport = async () => {
    try {
      message.loading({ content: '正在导出...', key: 'exporting' });
      const response = await apiClient.get('/admin/companies/export/', {
        params,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `企业列表_${new Date().toLocaleDateString()}.xlsx`);
      document.body.appendChild(link);
      link.click();
      message.success({ content: '导出成功', key: 'exporting' });
    } catch (error) {
      message.error({ content: '导出失败', key: 'exporting' });
    }
  };

  return (
    <div className="company-list-page">
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>企业信息管理</h2>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增企业
          </Button>
          <Button icon={<ImportOutlined />} onClick={() => setImportVisible(true)}>批量导入</Button>
          <Button icon={<ExportOutlined />} onClick={handleExport}>
            导出 Excel
          </Button>
        </Space>
      </div>

      <SearchForm
        onSearch={handleSearch}
        onReset={handleReset}
        loading={companyQuery.isFetching}
      />

      <DataTable
        data={companyQuery.data?.results || []}
        loading={companyQuery.isLoading}
        pagination={{ showQuickJumper: true,
          current: params.page,
          pageSize: 20,
          total: companyQuery.data?.count || 0,
        }}
        onEdit={handleEdit}
        onDelete={(id) => deleteMutation.mutate(id)}
        onChange={handleTableChange}
      />

      <ActionModal
        open={modalVisible}
        editingRecord={editingRecord}
        loading={saveMutation.isPending}
        onCancel={() => setModalVisible(false)}
        onOk={(values) => {
          saveMutation.mutate(values, {
            onSuccess: () => setModalVisible(false),
          });
        }}
      />

      <ImportModal
        open={importVisible}
        onCancel={() => setImportVisible(false)}
        onSuccess={() => {
          companyQuery.refetch();
        }}
      />
    </div>
  );
};

export default CompanyListPage;
