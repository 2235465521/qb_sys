import React, { useState, useEffect } from 'react';
import { 
  Card, Table, Tag, Input, Select, Button, Space, Modal, Form, 
  Popconfirm, Drawer, Row, Col, Timeline, Upload, 
  Radio, Checkbox, Divider, Typography, Avatar, Badge, Image, Tooltip
} from 'antd';
import { 
  SearchOutlined, UserOutlined, PhoneOutlined, WechatOutlined, 
  MessageOutlined, CalendarOutlined, EditOutlined, DeleteOutlined, 
  BankOutlined, CustomerServiceOutlined, FilterOutlined, PlusOutlined,
  DownloadOutlined, PaperClipOutlined, FilePdfOutlined,
  FileWordOutlined, FileImageOutlined, FileExcelOutlined, FileUnknownOutlined,
  InfoCircleOutlined, SettingOutlined, EyeOutlined, HistoryOutlined
} from '@ant-design/icons';
import { useCompanyLeads } from '@/hooks/useCompanyLeads';
import type { Lead, FollowUp, Attachment } from '@/hooks/useCompanyLeads';
import apiClient from '@/api/client';

const { Option } = Select;
const { TextArea } = Input;
const { Text, Paragraph } = Typography;

const AdminLeadsPage: React.FC = () => {
  const [params, setParams] = useState({ page: 1, keyword: '', status: '', source: '' });
  
  // Modals & Drawer States
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [detailsDrawerOpen, setDetailsDrawerOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  
  // Selection
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

  // Forms
  const [createForm] = Form.useForm();
  const [detailsForm] = Form.useForm();
  const [exportForm] = Form.useForm();

  // Dynamic Data Lists
  const [companies, setCompanies] = useState<any[]>([]);
  const [companyLoading, setCompanyLoading] = useState(false);
  const [users, setUsers] = useState<any[]>([]);
  
  // File Upload State
  const [createFiles, setCreateFiles] = useState<any[]>([]);
  const [followupText, setFollowupText] = useState('');
  const [followupFiles, setFollowupFiles] = useState<any[]>([]);

  const { 
    useAdminLeads, 
    createAdminLeadMutation, 
    updateLeadMutation, 
    deleteLeadMutation,
    addFollowUpMutation 
  } = useCompanyLeads();

  const { data, isLoading, refetch } = useAdminLeads(params);

  // Load companies & users
  const fetchUsers = async () => {
    try {
      const response = await apiClient.get('/admin/users/');
      if (Array.isArray(response.data)) {
        setUsers(response.data);
      } else if (response.data && (response.data as any).results) {
        setUsers((response.data as any).results);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const searchCompanies = async (kw: string) => {
    setCompanyLoading(true);
    try {
      const { data } = await apiClient.get('/admin/companies/', {
        params: { keyword: kw, page_size: 30 }
      });
      setCompanies(data.results || []);
    } catch (err) {
      console.error(err);
    } finally {
      setCompanyLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    searchCompanies('');
  }, []);

  const handleSearch = (value: string) => {
    setParams({ ...params, page: 1, keyword: value.trim() });
  };

  const handleFilterChange = (field: 'status' | 'source', value: string) => {
    setParams({ ...params, page: 1, [field]: value });
  };

  const handleOpenDetails = (lead: Lead) => {
    setSelectedLead(lead);
    detailsForm.setFieldsValue({
      status: lead.status,
      source: lead.source,
      req_type: lead.req_type,
      assignee: lead.assignee,
      enterprise: lead.enterprise,
      contact_name: lead.contact_name,
      contact_phone: lead.contact_phone,
      contact_wechat: lead.contact_wechat,
    });
    setFollowupText('');
    setFollowupFiles([]);
    setDetailsDrawerOpen(true);
  };

  const handleUpdateDetails = async (values: any) => {
    if (!selectedLead || !selectedLead.id) return;
    try {
      const updated = await updateLeadMutation.mutateAsync({
        id: selectedLead.id,
        ...values
      });
      setSelectedLead(updated);
      refetch();
    } catch (err) {}
  };

  const handleAddFollowup = async () => {
    if (!selectedLead || !selectedLead.id) return;
    if (!followupText.trim() && followupFiles.length === 0) {
      return;
    }

    const formData = new FormData();
    if (followupText.trim()) {
      formData.append('content', followupText.trim());
    }
    followupFiles.forEach((file) => {
      if (file.originFileObj) {
        formData.append('files', file.originFileObj);
      }
    });

    try {
      const updatedLead = await addFollowUpMutation.mutateAsync({
        leadId: selectedLead.id,
        formData
      });
      setSelectedLead(updatedLead);
      setFollowupText('');
      setFollowupFiles([]);
      refetch();
    } catch (err) {}
  };

  const handleCreateLead = async (values: any) => {
    const formData = new FormData();
    formData.append('source', values.source);
    formData.append('req_type', values.req_type);
    formData.append('status', values.status || 'pending');
    formData.append('contact_name', values.contact_name);
    formData.append('contact_phone', values.contact_phone);
    if (values.contact_wechat) {
      formData.append('contact_wechat', values.contact_wechat);
    }
    if (values.assignee) {
      formData.append('assignee', values.assignee.toString());
    }
    if (values.enterprise) {
      formData.append('enterprise', values.enterprise.toString());
    }
    createFiles.forEach((file) => {
      if (file.originFileObj) {
        formData.append('files', file.originFileObj);
      }
    });

    try {
      await createAdminLeadMutation.mutateAsync(formData);
      setCreateModalOpen(false);
      createForm.resetFields();
      setCreateFiles([]);
    } catch (err) {}
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteLeadMutation.mutateAsync(id);
      setSelectedRowKeys(selectedRowKeys.filter(k => k !== id));
      if (selectedLead?.id === id) {
        setDetailsDrawerOpen(false);
      }
    } catch (err) {}
  };

  const handleExport = async (values: any) => {
    try {
      const payload: any = {
        export_scope: values.export_scope,
        selected_fields: values.selected_fields,
      };

      if (values.export_scope === 'selected') {
        payload.ids = selectedRowKeys;
      } else {
        payload.filters = {
          keyword: params.keyword,
          status: params.status,
          source: params.source,
        };
      }

      const response = await apiClient.post('/admin/companies/leads/export/', payload, {
        responseType: 'blob'
      });

      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' 
      });
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = `线索高级定制导出_${new Date().toISOString().slice(0, 10)}.xlsx`;
      link.click();
      setExportModalOpen(false);
    } catch (err) {
      console.error(err);
    }
  };

  // Helper formatting / tagging
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return <FilePdfOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />;
      case 'doc':
      case 'docx':
        return <FileWordOutlined style={{ color: '#1890ff', fontSize: 18 }} />;
      case 'xls':
      case 'xlsx':
        return <FileExcelOutlined style={{ color: '#52c41a', fontSize: 18 }} />;
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
        return <FileImageOutlined style={{ color: '#fa8c16', fontSize: 18 }} />;
      default:
        return <FileUnknownOutlined style={{ color: '#8c8c8c', fontSize: 18 }} />;
    }
  };

  const isImageFile = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    return ext ? ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) : false;
  };

  const getSourceTag = (source: string, display: string) => {
    switch (source) {
      case 'wechat':
        return <Tag color="green" style={{ borderRadius: 4 }}>公众号/视频号</Tag>;
      case 'phone':
        return <Tag color="purple" style={{ borderRadius: 4 }}>电话咨询</Tag>;
      case 'visit':
        return <Tag color="geekblue" style={{ borderRadius: 4 }}>线下拜访</Tag>;
      default:
        return <Tag color="default" style={{ borderRadius: 4 }}>{display || '其他'}</Tag>;
    }
  };

  const getReqTypeTag = (type: string, display: string) => {
    switch (type) {
      case 'data_correction':
        return <Tag color="gold" style={{ borderRadius: 4 }}>数据纠错</Tag>;
      case 'business_cooperation':
        return <Tag color="orange" style={{ borderRadius: 4 }}>业务合作</Tag>;
      case 'general_inquiry':
        return <Tag color="blue" style={{ borderRadius: 4 }}>常规咨询</Tag>;
      default:
        return <Tag color="default" style={{ borderRadius: 4 }}>{display || '常规'}</Tag>;
    }
  };

  const getStatusTag = (status: string, display: string) => {
    switch (status) {
      case 'pending':
        return <Tag color="error" style={{ borderRadius: 4 }}>● {display || '待处理'}</Tag>;
      case 'following':
        return <Tag color="warning" style={{ borderRadius: 4 }}>● {display || '跟进中'}</Tag>;
      case 'solved':
        return <Tag color="success" style={{ borderRadius: 4 }}>● {display || '已成单'}</Tag>;
      case 'closed':
        return <Tag color="default" style={{ borderRadius: 4 }}>● {display || '已关闭'}</Tag>;
      default:
        return <Tag color="default" style={{ borderRadius: 4 }}>● {display}</Tag>;
    }
  };

  const columns = [
    {
      title: '意向企业画像',
      key: 'company',
      render: (record: Lead) => (
        <Space direction="vertical" size={2}>
          <div style={{ fontWeight: 'bold', fontSize: 14, color: '#1890ff' }}>
            <BankOutlined /> {record.enterprise_name || '非关联企业客户'}
          </div>
          {record.enterprise_credit_code && (
            <div style={{ fontSize: 11, color: '#8c8c8c', fontFamily: 'monospace' }}>
              信用代码: {record.enterprise_credit_code}
            </div>
          )}
        </Space>
      ),
    },
    {
      title: '诉求类型',
      dataIndex: 'req_type',
      key: 'req_type',
      width: 130,
      render: (type: string, record: Lead) => getReqTypeTag(type, record.req_type_display || type),
    },
    {
      title: '渠道来源',
      dataIndex: 'source',
      key: 'source',
      width: 140,
      render: (source: string, record: Lead) => getSourceTag(source, record.source_display || source),
    },
    {
      title: '联系人信息',
      key: 'contact',
      width: 190,
      render: (record: Lead) => (
        <Space direction="vertical" size={2} style={{ fontSize: 12 }}>
          <div>
            <UserOutlined style={{ color: '#8c8c8c' }} /> <span style={{ fontWeight: 500 }}>{record.contact_name || '--'}</span>
          </div>
          <div>
            <PhoneOutlined style={{ color: '#8c8c8c' }} /> <span>{record.contact_phone || '--'}</span>
          </div>
          {record.contact_wechat && (
            <div>
              <WechatOutlined style={{ color: '#52c41a' }} /> <span style={{ color: '#52c41a', fontFamily: 'monospace' }}>{record.contact_wechat}</span>
            </div>
          )}
        </Space>
      ),
    },
    {
      title: '当前负责人',
      dataIndex: 'assignee_name',
      key: 'assignee_name',
      width: 120,
      render: (name: string) => name ? (
        <Space size={6}>
          <Avatar size={20} icon={<UserOutlined />} style={{ backgroundColor: '#1890ff' }} />
          <span style={{ fontSize: 13, color: '#262626' }}>{name}</span>
        </Space>
      ) : (
        <Text type="secondary" style={{ fontSize: 12 }}>未分配</Text>
      ),
    },
    {
      title: '跟进进度',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string, record: Lead) => getStatusTag(status, record.status_display || status),
    },
    {
      title: '建档时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 155,
      render: (date: string) => (
        <span style={{ fontSize: 12, color: '#8c8c8c' }}>
          <CalendarOutlined /> {date ? new Date(date).toLocaleString('zh-CN', { hour12: false }) : '--'}
        </span>
      ),
    },
    {
      title: '管理操作',
      key: 'actions',
      width: 150,
      fixed: 'right' as const,
      render: (record: Lead) => (
        <Space size={12}>
          <Button
            type="link"
            icon={<EditOutlined />}
            style={{ padding: 0 }}
            onClick={() => handleOpenDetails(record)}
          >
            跟进详情
          </Button>
          <Popconfirm
            title="您确定要彻底删除该客户线索及所有的附件、跟进日志吗？此操作无法撤销！"
            onConfirm={() => handleDelete(record.id!)}
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              style={{ padding: 0 }}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="admin-leads-page" style={{ padding: '8px' }}>
      {/* Premium Gradient Banner */}
      <div 
        style={{ 
          marginBottom: 16, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #1f4e79 0%, #0d2c4d 100%)',
          padding: '20px 24px',
          borderRadius: 12,
          boxShadow: '0 4px 15px rgba(13,44,77,0.15)',
          color: '#ffffff'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ background: 'rgba(255,255,255,0.15)', padding: 10, borderRadius: 10, display: 'flex', alignItems: 'center' }}>
            <CustomerServiceOutlined style={{ fontSize: 24, color: '#ffffff' }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#ffffff', fontWeight: 'bold' }}>线索与商机管理 (CRM 销售漏斗)</h2>
            <p style={{ margin: '4px 0 0 0', fontSize: 12, color: 'rgba(255,255,255,0.85)' }}>
              统一分配意向客户。管理并记录从前台质询，数据纠错至签约转化的全生命周期跟进事件、凭证存档与日志留痕。
            </p>
          </div>
        </div>
        <Space size={12}>
          <Button 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={() => {
              createForm.resetFields();
              setCreateFiles([]);
              setCreateModalOpen(true);
            }}
            style={{ backgroundColor: '#52c41a', borderColor: '#52c41a', fontWeight: 500 }}
          >
            新建客户线索
          </Button>
          <Button 
            icon={<DownloadOutlined />}
            onClick={() => {
              exportForm.setFieldsValue({
                export_scope: selectedRowKeys.length > 0 ? 'selected' : 'query',
                selected_fields: ['source', 'req_type', 'status', 'assignee', 'enterprise', 'contact_name', 'contact_phone', 'created_at']
              });
              setExportModalOpen(true);
            }}
            style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: '#ffffff', fontWeight: 500 }}
            className="premium-export-btn"
          >
            高级导出 {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
          </Button>
        </Space>
      </div>

      {/* Filter panel */}
      <Card bordered={false} style={{ marginBottom: 16, borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.015)' }} bodyStyle={{ padding: 16 }}>
        <Space wrap size={20}>
          <Input.Search
            placeholder="搜联系人 / 电话 / 微信 / 企业..."
            allowClear
            onSearch={handleSearch}
            style={{ width: 280 }}
            enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
          />
          
          <Space>
            <span style={{ color: '#595959', fontSize: 13 }}><FilterOutlined /> 诉求过滤：</span>
            <Select 
              value={params.source} 
              onChange={(val) => handleFilterChange('source', val)} 
              style={{ width: 140 }}
            >
              <Option value="">所有渠道</Option>
              <Option value="wechat">公众号/视频号</Option>
              <Option value="phone">电话咨询</Option>
              <Option value="visit">线下拜访</Option>
              <Option value="other">其他</Option>
            </Select>
          </Space>

          <Space>
            <span style={{ color: '#595959', fontSize: 13 }}><FilterOutlined /> 跟进进度：</span>
            <Select 
              value={params.status} 
              onChange={(val) => handleFilterChange('status', val)} 
              style={{ width: 130 }}
            >
              <Option value="">所有状态</Option>
              <Option value="pending">待处理</Option>
              <Option value="following">跟进中</Option>
              <Option value="solved">已解决/已成单</Option>
              <Option value="closed">无效关闭</Option>
            </Select>
          </Space>
        </Space>
      </Card>

      {/* Table */}
      <Card bordered={false} style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.02)' }} bodyStyle={{ padding: 0 }}>
        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys)
          }}
          dataSource={data?.results || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ 
            showQuickJumper: true,
            current: params.page,
            pageSize: 20,
            total: data?.count || 0,
            onChange: (page) => setParams({ ...params, page }),
            showSizeChanger: false,
            showTotal: (total) => `共 ${total} 条销售线索`
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* Create Lead Modal */}
      <Modal
        title={
          <Space>
            <PlusOutlined style={{ color: '#52c41a' }} />
            <span style={{ fontWeight: 'bold' }}>新建 CRM 客户销售线索</span>
          </Space>
        }
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={null}
        width={600}
        destroyOnClose
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateLead}
          initialValues={{ status: 'pending', source: 'other', req_type: 'general_inquiry' }}
          style={{ marginTop: 16 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="source"
                label="渠道来源"
                rules={[{ required: true, message: '请选择渠道' }]}
              >
                <Select>
                  <Option value="wechat">公众号/视频号</Option>
                  <Option value="phone">电话咨询</Option>
                  <Option value="visit">线下拜访</Option>
                  <Option value="other">其他渠道</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="req_type"
                label="诉求类型"
                rules={[{ required: true, message: '请选择诉求类型' }]}
              >
                <Select>
                  <Option value="general_inquiry">常规咨询</Option>
                  <Option value="data_correction">数据纠错</Option>
                  <Option value="business_cooperation">业务合作</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="assignee" label="指派负责人">
                <Select placeholder="搜索指派负责人" allowClear>
                  {users.map(u => (
                    <Option key={u.id} value={u.id}>{u.real_name || u.username}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="enterprise" label="关联企业主表">
                <Select
                  showSearch
                  placeholder="检索匹配库中企业"
                  filterOption={false}
                  onSearch={searchCompanies}
                  loading={companyLoading}
                  allowClear
                >
                  {companies.map(c => (
                    <Option key={c.id} value={c.id}>{c.name}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider style={{ margin: '8px 0 16px 0' }} />

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="contact_name"
                label="联系人姓名"
                rules={[{ required: true, message: '请输入姓名' }]}
              >
                <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} placeholder="联系人" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="contact_phone"
                label="联系电话"
                rules={[{ required: true, message: '请输入电话' }]}
              >
                <Input prefix={<PhoneOutlined style={{ color: '#bfbfbf' }} />} placeholder="电话/手机" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="contact_wechat" label="联系微信">
                <Input prefix={<WechatOutlined style={{ color: '#bfbfbf' }} />} placeholder="微信号" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item label="附件上传 (凭证、合规授权书等，支持拖拽多选)">
            <Upload.Dragger
              multiple
              fileList={createFiles}
              onChange={(info) => setCreateFiles(info.fileList)}
              beforeUpload={() => false} // Manual upload
            >
              <p className="ant-upload-drag-icon">
                <PaperClipOutlined style={{ color: '#1890ff', fontSize: 28 }} />
              </p>
              <p className="ant-upload-text" style={{ fontSize: 13 }}>点击或将文件拖拽到此区域上传</p>
              <p className="ant-upload-hint" style={{ fontSize: 11, color: '#8c8c8c' }}>支持 PDF, Images, Word, Excel 文件，大小限制单文件 15MB</p>
            </Upload.Dragger>
          </Form.Item>

          <div style={{ textAlign: 'right', borderTop: '1px solid #f0f0f0', paddingTop: 16, marginTop: 24 }}>
            <Button onClick={() => setCreateModalOpen(false)} style={{ marginRight: 8 }}>
              取消
            </Button>
            <Button type="primary" htmlType="submit" loading={createAdminLeadMutation.isPending}>
              保存并指派
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Advanced Custom Export Modal */}
      <Modal
        title={
          <Space>
            <DownloadOutlined style={{ color: '#1890ff' }} />
            <span style={{ fontWeight: 'bold' }}>高级数据定制导出</span>
          </Space>
        }
        open={exportModalOpen}
        onCancel={() => setExportModalOpen(false)}
        footer={null}
        width={500}
        destroyOnClose
      >
        <Form
          form={exportForm}
          layout="vertical"
          onFinish={handleExport}
          style={{ marginTop: 12 }}
        >
          <Form.Item
            name="export_scope"
            label="导出数据范围"
            rules={[{ required: true }]}
          >
            <Radio.Group>
              <Radio value="query">导出当前检索条件下的所有数据 ({data?.count || 0} 条)</Radio>
              <Radio value="selected" disabled={selectedRowKeys.length === 0}>
                导出表格中选中的数据 ({selectedRowKeys.length} 条)
              </Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            name="selected_fields"
            label="自定义选择导出字段（按需导出）"
            rules={[{ required: true, message: '请至少选择一个导出字段' }]}
          >
            <Checkbox.Group style={{ width: '100%' }}>
              <Row gutter={[12, 12]}>
                <Col span={12}><Checkbox value="enterprise">关联企业名称</Checkbox></Col>
                <Col span={12}><Checkbox value="req_type">诉求类型</Checkbox></Col>
                <Col span={12}><Checkbox value="source">渠道来源</Checkbox></Col>
                <Col span={12}><Checkbox value="status">跟进状态</Checkbox></Col>
                <Col span={12}><Checkbox value="assignee">当前负责人</Checkbox></Col>
                <Col span={12}><Checkbox value="contact_name">联系人姓名</Checkbox></Col>
                <Col span={12}><Checkbox value="contact_phone">联系电话</Checkbox></Col>
                <Col span={12}><Checkbox value="contact_wechat">联系微信</Checkbox></Col>
                <Col span={12}><Checkbox value="created_at">建立时间</Checkbox></Col>
                <Col span={12}><Checkbox value="updated_at">更新时间</Checkbox></Col>
              </Row>
            </Checkbox.Group>
          </Form.Item>

          <div style={{ textAlign: 'right', borderTop: '1px solid #f0f0f0', paddingTop: 16, marginTop: 24 }}>
            <Button onClick={() => setExportModalOpen(false)} style={{ marginRight: 8 }}>
              取消
            </Button>
            <Button type="primary" htmlType="submit" icon={<DownloadOutlined />}>
              开始打包导出 Excel
            </Button>
          </div>
        </Form>
      </Modal>

      {/* Lead Details & Timeline Drawer */}
      <Drawer
        title={
          selectedLead ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '95%' }}>
              <Space>
                <HistoryOutlined style={{ color: '#1890ff' }} />
                <span style={{ fontWeight: 'bold' }}>【{selectedLead.contact_name}】的线索客户跟进详情</span>
              </Space>
              <Badge status={selectedLead.status === 'solved' ? 'success' : selectedLead.status === 'closed' ? 'default' : 'processing'} text={selectedLead.status_display} />
            </div>
          ) : '线索详情'
        }
        width={960}
        onClose={() => setDetailsDrawerOpen(false)}
        open={detailsDrawerOpen}
        destroyOnClose
        bodyStyle={{ padding: '24px 32px', backgroundColor: '#f8fafc' }}
      >
        {selectedLead && (
          <Row gutter={24} style={{ height: '100%' }}>
            {/* Left Panel - Editable fields form */}
            <Col span={10}>
              <Card 
                title={<span style={{ fontWeight: 600 }}><UserOutlined /> 线索基本信息</span>}
                bordered={false}
                style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}
              >
                <Form
                  form={detailsForm}
                  layout="vertical"
                  onValuesChange={handleUpdateDetails}
                >
                  <Form.Item name="status" label="跟进状态" rules={[{ required: true }]}>
                    <Select>
                      <Option value="pending">待处理</Option>
                      <Option value="following">跟进中</Option>
                      <Option value="solved">已解决/已成单</Option>
                      <Option value="closed">无效关闭</Option>
                    </Select>
                  </Form.Item>

                  <Form.Item name="assignee" label="指派负责人">
                    <Select placeholder="指派跟进人员" allowClear>
                      {users.map(u => (
                        <Option key={u.id} value={u.id}>{u.real_name || u.username}</Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Form.Item name="req_type" label="客户诉求类型">
                    <Select>
                      <Option value="general_inquiry">常规咨询</Option>
                      <Option value="data_correction">数据纠错</Option>
                      <Option value="business_cooperation">业务合作</Option>
                    </Select>
                  </Form.Item>

                  <Form.Item name="source" label="客户渠道来源">
                    <Select>
                      <Option value="wechat">公众号/视频号</Option>
                      <Option value="phone">电话咨询</Option>
                      <Option value="visit">线下拜访</Option>
                      <Option value="other">其他渠道</Option>
                    </Select>
                  </Form.Item>

                  <Form.Item name="enterprise" label="关联企业库企业">
                    <Select
                      showSearch
                      placeholder="关联现有企业"
                      filterOption={false}
                      onSearch={searchCompanies}
                      loading={companyLoading}
                      allowClear
                    >
                      {companies.map(c => (
                        <Option key={c.id} value={c.id}>{c.name}</Option>
                      ))}
                    </Select>
                  </Form.Item>

                  <Divider style={{ margin: '12px 0' }} />

                  <Form.Item name="contact_name" label="联系人姓名" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>

                  <Form.Item name="contact_phone" label="联系电话" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>

                  <Form.Item name="contact_wechat" label="联系微信">
                    <Input />
                  </Form.Item>
                </Form>
              </Card>
            </Col>

            {/* Right Panel - Timeline, Logs & Attachments Upload */}
            <Col span={14} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Timeline Card */}
              <Card 
                title={<span style={{ fontWeight: 600 }}><HistoryOutlined style={{ color: '#1890ff' }} /> 跟进动态时间轴</span>}
                bordered={false}
                style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.03)', flex: '1 1 auto', overflowY: 'auto' }}
                bodyStyle={{ maxHeight: 350, overflowY: 'auto' }}
              >
                {selectedLead.followups && selectedLead.followups.length > 0 ? (
                  <Timeline mode="left" style={{ marginTop: 12 }}>
                    {selectedLead.followups.map((f: FollowUp) => {
                      const isSystem = f.content.startsWith('[系统日志]');
                      return (
                        <Timeline.Item 
                          key={f.id} 
                          color={isSystem ? 'gray' : 'blue'}
                          dot={isSystem ? <SettingOutlined style={{ fontSize: 13, color: '#8c8c8c' }} /> : <MessageOutlined style={{ fontSize: 13, color: '#1890ff' }} />}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                            <Text strong style={{ fontSize: 12, color: isSystem ? '#8c8c8c' : '#262626' }}>
                              {isSystem ? '系统自动日志' : f.creator_name || '跟进人员'}
                            </Text>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {new Date(f.created_at).toLocaleString()}
                            </Text>
                          </div>
                          <Paragraph style={{ margin: 0, fontSize: 13, color: isSystem ? '#8c8c8c' : '#595959', whiteSpace: 'pre-wrap' }}>
                            {f.content}
                          </Paragraph>
                        </Timeline.Item>
                      );
                    })}
                  </Timeline>
                ) : (
                  <div style={{ textAlign: 'center', padding: '32px 0', color: '#bfbfbf' }}>
                    <InfoCircleOutlined style={{ fontSize: 24, marginBottom: 8 }} />
                    <div>暂无任何跟进记录，请在下方添加首条沟通日志。</div>
                  </div>
                )}
              </Card>

              {/* Follow-up submission Card */}
              <Card
                title={<span style={{ fontWeight: 600 }}><PlusOutlined style={{ color: '#1890ff' }} /> 追加跟进与附件</span>}
                bordered={false}
                style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}
                bodyStyle={{ padding: 16 }}
              >
                <TextArea
                  rows={3}
                  value={followupText}
                  onChange={(e) => setFollowupText(e.target.value)}
                  placeholder="记录本次电话细节、客户反馈、报价谈判细节等..."
                  style={{ marginBottom: 12 }}
                />

                <Row justify="space-between" align="middle">
                  <Col>
                    <Upload
                      multiple
                      fileList={followupFiles}
                      onChange={(info) => setFollowupFiles(info.fileList)}
                      beforeUpload={() => false}
                    >
                      <Button icon={<PaperClipOutlined />} size="small">上传附件</Button>
                    </Upload>
                  </Col>
                  <Col>
                    <Button 
                      type="primary" 
                      onClick={handleAddFollowup}
                      loading={addFollowUpMutation.isPending}
                      disabled={!followupText.trim() && followupFiles.length === 0}
                    >
                      提交跟进记录
                    </Button>
                  </Col>
                </Row>
              </Card>

              {/* Attachments view list */}
              <Card
                title={<span style={{ fontWeight: 600 }}><PaperClipOutlined style={{ color: '#1890ff' }} /> 线索关联文件 ({selectedLead.attachments?.length || 0})</span>}
                bordered={false}
                style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}
                bodyStyle={{ padding: 12 }}
              >
                {selectedLead.attachments && selectedLead.attachments.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {/* Image Attachments section */}
                    {selectedLead.attachments.some(att => isImageFile(att.filename)) && (
                      <div style={{ marginBottom: 8 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#595959', marginBottom: 8 }}>
                          图片存证 (点击可直接预览/旋转)
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                          <Image.PreviewGroup>
                            {selectedLead.attachments.filter(att => isImageFile(att.filename)).map(att => (
                              <div key={att.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <Image
                                  src={att.file_url || att.file}
                                  alt={att.filename}
                                  width={80}
                                  height={80}
                                  style={{ objectFit: 'cover', borderRadius: 8, border: '1px solid #f0f0f0' }}
                                />
                                <Tooltip title={att.filename}>
                                  <div style={{ fontSize: 10, color: '#8c8c8c', textAlign: 'center', marginTop: 4, maxWidth: 80, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {att.filename}
                                  </div>
                                </Tooltip>
                              </div>
                            ))}
                          </Image.PreviewGroup>
                        </div>
                        {selectedLead.attachments.some(att => !isImageFile(att.filename)) && (
                          <Divider style={{ margin: '16px 0 12px 0' }} />
                        )}
                      </div>
                    )}
                    
                    {/* Document Attachments section */}
                    {selectedLead.attachments.some(att => !isImageFile(att.filename)) && (
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#595959', marginBottom: 8 }}>
                          文档资料
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          {selectedLead.attachments.filter(att => !isImageFile(att.filename)).map((att: Attachment) => (
                            <div 
                              key={att.id} 
                              style={{ 
                                display: 'flex', 
                                justifyContent: 'space-between', 
                                alignItems: 'center',
                                padding: '8px 12px',
                                background: '#ffffff',
                                borderRadius: 8,
                                border: '1px solid #f0f0f0'
                              }}
                            >
                              <Space>
                                {getFileIcon(att.filename)}
                                <div style={{ display: 'flex', flexDirection: 'column' }}>
                                  <Text strong style={{ fontSize: 12, maxWidth: 300 }} ellipsis={{ tooltip: att.filename }}>
                                    {att.filename}
                                  </Text>
                                  <Text type="secondary" style={{ fontSize: 10 }}>
                                    {formatBytes(att.size)} · 上传于 {new Date(att.created_at).toLocaleDateString()}
                                  </Text>
                                </div>
                              </Space>
                              <Button 
                                type="text" 
                                icon={<EyeOutlined />} 
                                onClick={() => window.open(att.file_url || att.file, '_blank')}
                              >
                                预览 / 下载
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '16px 0', color: '#bfbfbf', fontSize: 12 }}>
                    暂无任何存证文件。
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        )}
      </Drawer>
    </div>
  );
};

export default AdminLeadsPage;

