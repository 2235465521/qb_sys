import React, { useState } from 'react';
import { Button, Space, message, Modal, Checkbox, Switch, Row, Col, Divider, Radio, Select, Form, Tooltip } from 'antd';
import { PlusOutlined, ExportOutlined, ImportOutlined, TagsOutlined } from '@ant-design/icons';
import SearchForm from './components/SearchForm';
import DataTable from './components/DataTable';
import ActionModal from './components/ActionModal';
import ImportModal from './components/ImportModal';
import { useCompanyData } from '@/hooks/useCompanyData';
import { useDictData } from '@/hooks/useDictData';
import type { Company, CompanySearchParams } from '@/types';
import apiClient from '@/api/client';

const EXPORT_FIELDS_OPTIONS = [
  { label: '企业名称', value: 'name' },
  { label: '信用代码', value: 'credit_code' },
  { label: '法人', value: 'legal_person' },
  { label: '省份', value: 'province' },
  { label: '城市', value: 'city' },
  { label: '区县', value: 'district' },
  { label: '所有制大类', value: 'ownership_category' },
  { label: '所有制标签', value: 'ownership_tags' },
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
  { label: '曾用名', value: 'former_names' },
  { label: '企业官网', value: 'website_url' },
  { label: '通讯地址', value: 'mailing_address' },
  { label: '通讯邮编', value: 'mailing_address_zip' },
  { label: '经营范围', value: 'business_scope' },
  { label: '登记状态', value: 'registration_status' }
];

// 定义预设模板字段集合
const PRESETS = {
  basic: ['name', 'credit_code', 'legal_person', 'province', 'city', 'district', 'address', 'status', 'created_at'],
  contact: ['name', 'contact', 'valid_mobile', 'more_phones', 'email'],
  all: EXPORT_FIELDS_OPTIONS.map(o => o.value)
};

const CompanyListPage: React.FC = () => {
  const [params, setParams] = useState<CompanySearchParams>({ page: 1 });
  const [modalVisible, setModalVisible] = useState(false);
  const [importVisible, setImportVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Company | null>(null);
  const [isViewOnly, setIsViewOnly] = useState(false);

  // 表格复选框勾选的行 ID 列表
  const [selectedRowKeys, setSelectedRowKeys] = useState<number[]>([]);

  // 导出配置 Modal 状态
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportScope, setExportScope] = useState<'selected' | 'query'>('query');
  const [exportFields, setExportFields] = useState<string[]>(EXPORT_FIELDS_OPTIONS.map(o => o.value));
  const [includeStandards, setIncludeStandards] = useState(false);
  const [exporting, setExporting] = useState(false);

  // 批量打标签 Modal 状态
  const [batchTagModalVisible, setBatchTagModalVisible] = useState(false);
  const [batchTagging, setBatchTagging] = useState(false);
  const [batchTagForm] = Form.useForm();

  const { categoryQuery } = useDictData();
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

  const handleSyncOwnership = async (record: Company) => {
    message.loading({ content: `正在智能识别【${record.name}】的所有制与属性标签...`, key: 'sync_tag' });
    try {
      const res = await apiClient.post(`/admin/companies/${record.id}/sync_ownership/`, { use_qcc: false });
      message.success({ content: res.data.message || '识别成功并已保存！', key: 'sync_tag' });
      companyQuery.refetch();
    } catch (e) {
      message.error({ content: '智能识别失败', key: 'sync_tag' });
    }
  };

  const handleBatchTagSubmit = async () => {
    try {
      const values = await batchTagForm.validateFields();
      if (!selectedRowKeys || selectedRowKeys.length === 0) {
        message.warning('请先在表格中勾选企业');
        return;
      }
      setBatchTagging(true);
      const res = await apiClient.post('/admin/companies/batch_tag/', {
        company_ids: selectedRowKeys,
        category_ids: values.category_ids,
        action: values.action || 'add',
      });
      message.success(res.data.message || '批量打标签成功！');
      setBatchTagModalVisible(false);
      batchTagForm.resetFields();
      companyQuery.refetch();
    } catch (e: any) {
      message.error(e.response?.data?.error || '批量打标签失败');
    } finally {
      setBatchTagging(false);
    }
  };

  const handleExportClick = () => {
    // 默认根据是否有勾选行决定导出范围
    if (selectedRowKeys.length > 0) {
      setExportScope('selected');
    } else {
      setExportScope('query');
    }
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
      
      // 发送高级导出 POST 请求
      const response = await apiClient.post('/admin/companies/export/', {
        export_scope: exportScope,
        ids: exportScope === 'selected' ? selectedRowKeys : [],
        filters: params, // 将当前页面检索条件传入
        selected_fields: exportFields,
        include_standards: includeStandards,
      }, {
        responseType: 'blob',
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `企业高级定制导出_${new Date().toLocaleDateString()}.xlsx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      message.success({ content: '数据导出成功！', key: 'exporting' });
      setExportModalVisible(false);
    } catch (error: any) {
      message.error({ content: '导出失败，请重新尝试。', key: 'exporting' });
    } finally {
      setExporting(false);
    }
  };

  // 快捷操作：反选
  const handleInvertSelectFields = () => {
    const allFieldValues = EXPORT_FIELDS_OPTIONS.map(o => o.value);
    setExportFields(prev => allFieldValues.filter(val => !prev.includes(val)));
  };

  // 快捷应用预设模板
  const applyPresetTemplate = (type: 'basic' | 'contact' | 'all') => {
    setExportFields(PRESETS[type]);
  };

  return (
    <div className="company-list-page">
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>企业信息管理</h2>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增企业
          </Button>
          <Button
            icon={<TagsOutlined />}
            disabled={selectedRowKeys.length === 0}
            onClick={() => setBatchTagModalVisible(true)}
          >
            批量打标签 {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
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
        selectedRowKeys={selectedRowKeys}
        onSelectionChange={setSelectedRowKeys}
        onEdit={handleEdit}
        onViewDetails={handleViewDetails}
        onSyncOwnership={handleSyncOwnership}
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

      {/* 批量打标签弹窗 */}
      <Modal
        title={
          <Space>
            <TagsOutlined style={{ color: '#1890ff' }} />
            <span>批量设置企业所有制与属性标签</span>
          </Space>
        }
        open={batchTagModalVisible}
        onCancel={() => setBatchTagModalVisible(false)}
        onOk={handleBatchTagSubmit}
        confirmLoading={batchTagging}
        width={580}
        okText="确认应用"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ marginBottom: 16, color: '#666', background: '#f5f5f5', padding: '8px 12px', borderRadius: 4 }}>
          已选择 <b>{selectedRowKeys.length}</b> 家企业进行批量打标签操作。
        </div>
        <Form form={batchTagForm} layout="vertical" initialValues={{ action: 'add' }}>
          <Form.Item name="action" label="操作方式" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="add">追加标签（保留企业已有标签）</Radio>
              <Radio value="replace">全量覆盖（替换为所选标签）</Radio>
              <Radio value="remove">移除所选标签</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            name="category_ids"
            label="选择标签"
            rules={[{ required: true, message: '请至少选择一个所有制分类或标签' }]}
          >
            <Select
              mode="multiple"
              placeholder="请选择要赋予或移除的所有制大类与小类标签"
              style={{ width: '100%' }}
              loading={categoryQuery.isLoading}
              optionLabelProp="label"
            >
              {categoryQuery.data
                ?.filter(c => c.category_type === 'main')
                .map(mainCat => {
                  const subCats = categoryQuery.data?.filter(s => s.parent_id === mainCat.id);
                  return (
                    <Select.OptGroup key={mainCat.id} label={mainCat.name}>
                      <Select.Option key={mainCat.id} value={mainCat.id} label={mainCat.name}>
                        <Tooltip title={mainCat.definition} placement="right">
                          <div style={{ fontWeight: 'bold' }}>{mainCat.name} (主大类)</div>
                        </Tooltip>
                      </Select.Option>
                      {subCats?.map(sub => (
                        <Select.Option key={sub.id} value={sub.id} label={sub.name}>
                          <Tooltip title={sub.definition} placement="right">
                            <div style={{ paddingLeft: 12 }}>└─ {sub.name}</div>
                          </Tooltip>
                        </Select.Option>
                      ))}
                    </Select.OptGroup>
                  );
                })}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 模块二：高级导出配置弹窗 */}
      <Modal
        title={
          <Space>
            <ExportOutlined style={{ color: '#1890ff' }} />
            <span>高级数据导出</span>
          </Space>
        }
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        onOk={executeExport}
        confirmLoading={exporting}
        width={720}
        okText="确认导出"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ padding: '8px 0' }}>
          
          {/* 1. 导出范围配置 */}
          <div style={{ marginBottom: 20 }}>
            <span style={{ fontWeight: 600, display: 'block', marginBottom: 8, color: '#333' }}>1. 导出数据范围：</span>
            <Radio.Group 
              value={exportScope} 
              onChange={(e) => setExportScope(e.target.value)}
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              <Radio value="selected" disabled={selectedRowKeys.length === 0}>
                导出当前选中数据 <span style={{ color: '#1890ff', fontWeight: 'bold' }}>({selectedRowKeys.length} 条)</span>
                {selectedRowKeys.length === 0 && <span style={{ color: '#bfbfbf', fontSize: 12, marginLeft: 8 }}>(请在表格中先勾选行数据才能选用)</span>}
              </Radio>
              <Radio value="query">
                导出当前检索条件下的所有数据 <span style={{ color: '#52c41a', fontWeight: 'bold' }}>({companyQuery.data?.count || 0} 条)</span>
              </Radio>
            </Radio.Group>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          {/* 2. 导出字段配置 */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontWeight: 600, color: '#333' }}>2. 自定义导出字段属性：</span>
              
              {/* 字段勾选辅助按钮组 */}
              <Space size="small">
                <Button size="small" type="link" onClick={() => applyPresetTemplate('all')}>全选</Button>
                <Button size="small" type="link" onClick={() => setExportFields([])}>清空</Button>
                <Button size="small" type="link" onClick={handleInvertSelectFields}>反选</Button>
              </Space>
            </div>

            {/* 预设快捷模板选择 */}
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: '#8c8c8c' }}>预设配置模版：</span>
              <Space>
                <Button size="small" style={{ borderRadius: 12 }} onClick={() => applyPresetTemplate('basic')}>仅基本信息</Button>
                <Button size="small" style={{ borderRadius: 12 }} onClick={() => applyPresetTemplate('contact')}>仅联系方式</Button>
                <Button size="small" style={{ borderRadius: 12 }} onClick={() => applyPresetTemplate('all')}>导出全部字段</Button>
              </Space>
            </div>
            
            <Checkbox.Group 
              value={exportFields} 
              onChange={(checkedValues) => setExportFields(checkedValues as string[])}
              style={{ width: '100%' }}
            >
              <Row gutter={[12, 12]} style={{ maxHeight: 200, overflowY: 'auto', padding: '4px 0' }}>
                {EXPORT_FIELDS_OPTIONS.map((opt) => (
                  <Col span={6} key={opt.value}>
                    <Checkbox value={opt.value}>{opt.label}</Checkbox>
                  </Col>
                ))}
              </Row>
            </Checkbox.Group>
          </div>

          <Divider style={{ margin: '12px 0' }} />

          {/* 3. 级联数据配置 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0' }}>
            <div>
              <span style={{ fontWeight: 600, display: 'block', color: '#333' }}>3. 级联数据选项：是否同时导出企业关联的标准目录</span>
              <span style={{ fontSize: 12, color: '#8c8c8c' }}>启用后，将在 Excel 数据末尾自动生成“关联标准目录”列平铺显示所有关联标准信息</span>
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
