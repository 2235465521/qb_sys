import React, { useState } from 'react';
import { Button, Space, message, Modal, Checkbox, Switch, Row, Col, Divider } from 'antd';
import { PlusOutlined, ExportOutlined, ImportOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import DataTable from './components/DataTable';
import ActionModal from './components/ActionModal';
import ImportModal from './components/ImportModal';
import { useCompanyData } from '@/hooks/useCompanyData';
import type { Company, CompanySearchParams } from '@/types';
import apiClient from '@/api/client';

const EXPORT_FIELDS_OPTIONS = [
  { label: '企业名称', value: 'name' },
  { label: '信用代码', value: 'credit_code' },
  { label: '法人', value: 'legal_person' },
  { label: '省份', value: 'province' },
  { label: '城市', value: 'city' },
  { label: '区县', value: 'district' },
  { label: '经度', value: 'longitude' },
  { label: '纬度', value: 'latitude' },
  { label: '联系方式', value: 'contact' },
  { label: '详细地址', value: 'address' },
  { label: '状态', value: 'status' },
  { label: '入库时间', value: 'created_at' },
  // 新增字段
  { label: '成立日期', value: 'established_date' },
  { label: '注册地址', value: 'registered_address' },
  { label: '注册地址邮编', value: 'registered_zipcode' },
  { label: '有效手机号', value: 'valid_mobile' },
  { label: '更多电话', value: 'more_phones' },
  { label: '邮箱', value: 'email' },
  { label: '企业类型', value: 'company_type' },
  { label: '注册号', value: 'registration_no' },
  { label: '组织机构代码', value: 'organization_code' },
  { label: '行业门类', value: 'industry_category' },
  { label: '行业大类', value: 'industry_major' },
  { label: '行业中类', value: 'industry_middle' },
  { label: '行业小类', value: 'industry_minor' },
  { label: '企业规模', value: 'company_size' },
  { label: '英文名', value: 'english_name' },
  { label: '曾用名', value: 'former_names' }
];

const CompanyListPage: React.FC = () => {
  const [params, setParams] = useState<CompanySearchParams>({ page: 1 });
  const [modalVisible, setModalVisible] = useState(false);
  const [importVisible, setImportVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Company | null>(null);
  const [isViewOnly, setIsViewOnly] = useState(false);

  // 导出配置 Modal 状态
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportFields, setExportFields] = useState<string[]>(EXPORT_FIELDS_OPTIONS.map(o => o.value));
  const [includeStandards, setIncludeStandards] = useState(false);
  const [exporting, setExporting] = useState(false);

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
    setIsViewOnly(false);
    setModalVisible(true);
  };

  const handleEdit = (record: Company) => {
    setEditingRecord(record);
    setIsViewOnly(false);
    setModalVisible(true);
  };

  const handleViewDetails = (record: Company) => {
    setEditingRecord(record);
    setIsViewOnly(true);
    setModalVisible(true);
  };

  const handleExportClick = () => {
    setExportModalVisible(true);
  };

  const executeExport = async () => {
    if (exportFields.length === 0) {
      message.warning('请至少选择一个要导出的字段');
      return;
    }

    try {
      setExporting(true);
      message.loading({ content: '正在导出 Excel 数据...', key: 'exporting', duration: 0 });
      
      // 使用 POST 请求发送大对象数组 fields，解决 URL 参数过长的限制
      const response = await apiClient.post('/admin/companies/export/', {
        ...params,
        fields: exportFields,
        include_standards: includeStandards,
      }, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `企业数据导出_${new Date().toLocaleDateString()}.xlsx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      message.success({ content: '导出成功！', key: 'exporting' });
      setExportModalVisible(false);
    } catch (error) {
      message.error({ content: '导出失败，请重试', key: 'exporting' });
    } finally {
      setExporting(false);
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
          <Button type="primary" ghost icon={<ExportOutlined />} onClick={handleExportClick}>
            批量导出
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
        pagination={{ 
          showQuickJumper: true,
          current: params.page,
          pageSize: 20,
          total: companyQuery.data?.count || 0,
        }}
        onEdit={handleEdit}
        onViewDetails={handleViewDetails}
        onDelete={(id) => deleteMutation.mutate(id)}
        onChange={handleTableChange}
      />

      <ActionModal
        open={modalVisible}
        editingRecord={editingRecord}
        isViewOnly={isViewOnly}
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

      {/* 模块二：高级导出配置弹窗 */}
      <Modal
        title={
          <Space>
            <ExportOutlined style={{ color: '#1890ff' }} />
            <span>配置导出属性</span>
          </Space>
        }
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        onOk={executeExport}
        confirmLoading={exporting}
        width={680}
        okText="确认导出"
        cancelText="取消"
      >
        <div style={{ padding: '8px 0' }}>
          <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 500 }}>选择需要导出的字段：</span>
            <Checkbox
              checked={exportFields.length === EXPORT_FIELDS_OPTIONS.length}
              indeterminate={exportFields.length > 0 && exportFields.length < EXPORT_FIELDS_OPTIONS.length}
              onChange={(e) => {
                setExportFields(e.target.checked ? EXPORT_FIELDS_OPTIONS.map(o => o.value) : []);
              }}
            >
              全选
            </Checkbox>
          </div>
          
          <Checkbox.Group 
            value={exportFields} 
            onChange={(checkedValues) => setExportFields(checkedValues as string[])}
            style={{ width: '100%' }}
          >
            <Row gutter={[12, 12]}>
              {EXPORT_FIELDS_OPTIONS.map((opt) => (
                <Col span={6} key={opt.value}>
                  <Checkbox value={opt.value}>{opt.label}</Checkbox>
                </Col>
              ))}
            </Row>
          </Checkbox.Group>

          <Divider style={{ margin: '16px 0' }} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontWeight: 500, display: 'block' }}>是否同时导出该企业关联的标准目录</span>
              <span style={{ fontSize: 12, color: '#8c8c8c' }}>开启后，将在导出的 Excel 末尾自动追加该公司关联的所有“标准目录”列表</span>
            </div>
            <Switch 
              checked={includeStandards} 
              onChange={setIncludeStandards} 
              checkedChildren="是" 
              unCheckedChildren="否"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default CompanyListPage;
