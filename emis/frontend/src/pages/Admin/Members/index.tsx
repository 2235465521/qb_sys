import React, { useState } from 'react';
import { Table, Card, Button, Space, Modal, Form, Input, Select, Tag, Popconfirm, Typography, Row, Col, Tabs, Alert, Checkbox, message } from 'antd';
import { TeamOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, PlusOutlined, DownloadOutlined } from '@ant-design/icons';
import { useMemberAdminData } from '@/hooks/useMemberAdminData';
import type { Member } from '@/types';
import dayjs from 'dayjs';
import apiClient from '@/api/client';

const { Text } = Typography;

interface CustomFieldItem {
  key: string;
  value: string;
}

interface ParsedNotes {
  text: string;
  customFields: CustomFieldItem[];
}

const parseNotes = (notesStr: string): ParsedNotes => {
  try {
    const parsed = JSON.parse(notesStr);
    if (parsed && typeof parsed === 'object' && ('text' in parsed || 'customFields' in parsed)) {
      return {
        text: parsed.text || '',
        customFields: Array.isArray(parsed.customFields) ? parsed.customFields : [],
      };
    }
  } catch (e) {
    // Fallback
  }
  return {
    text: notesStr || '',
    customFields: [],
  };
};

const serializeNotes = (text: string, customFields: CustomFieldItem[]): string => {
  return JSON.stringify({
    text: text || '',
    customFields: customFields || [],
  });
};

const exportFields = [
  { label: '姓名', value: 'name' },
  { label: '联系电话', value: 'phone' },
  { label: '职务 (身兼多职)', value: 'position' },
  { label: '归属单位/组织', value: 'company' },
  { label: '备注说明', value: 'notes' },
  { label: '入库时间', value: 'created_at' },
];

const MemberAdminPage: React.FC = () => {
  const [params, setParams] = useState<{ page: number; keyword: string; category_code?: string }>({ 
    page: 1, 
    keyword: '',
    category_code: undefined 
  });
  const [modalVisible, setModalVisible] = useState(false);
  const [catModalVisible, setCatModalVisible] = useState(false);
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [selectedFields, setSelectedFields] = useState<string[]>(['name', 'phone', 'position', 'company']);
  const [exporting, setExporting] = useState(false);
  const [editingMember, setEditingMember] = useState<Member | null>(null);
  
  // 扩展自定义字段
  const [customFields, setCustomFields] = useState<CustomFieldItem[]>([]);

  // 一人多职列表项
  const [rolesList, setRolesList] = useState<{ id?: number; category: number; org_name: string; position: string }[]>([]);

  const { 
    memberQuery, 
    saveMemberMutation, 
    deleteMemberMutation,
    categoryQuery,
    createCategoryMutation
  } = useMemberAdminData(params);
  
  const [form] = Form.useForm();
  const [catForm] = Form.useForm();

  const handleSearch = (value: string) => {
    setParams({ ...params, keyword: value, page: 1 });
  };

  const handleReset = () => {
    setParams({ page: 1, keyword: '', category_code: undefined });
  };

  const handleAdd = () => {
    setEditingMember(null);
    form.resetFields();
    setCustomFields([]);
    setRolesList([{ category: categoryQuery.data?.[0]?.id || 1, org_name: '', position: '' }]);
    setModalVisible(true);
  };

  const handleEdit = (record: Member) => {
    setEditingMember(record);
    const parsed = parseNotes(record.notes);
    form.setFieldsValue({
      name: record.name,
      phone: record.phone,
      status: record.status,
      notes: parsed.text
    });
    setCustomFields(parsed.customFields);
    
    // 映射任职角色
    if (record.roles && record.roles.length > 0) {
      setRolesList(record.roles.map(r => ({
        id: r.id,
        category: r.category,
        org_name: r.org_name,
        position: r.position
      })));
    } else {
      setRolesList([{ category: categoryQuery.data?.[0]?.id || 1, org_name: '', position: '' }]);
    }

    setModalVisible(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const serializedNotes = serializeNotes(values.notes, customFields);
      
      // 过滤未填写的任职职位
      const filteredRoles = rolesList.filter(r => r.category && r.org_name.trim());

      saveMemberMutation.mutate({ 
        ...editingMember, 
        name: values.name,
        phone: values.phone,
        status: values.status,
        notes: serializedNotes,
        roles: filteredRoles as any
      }, {
        onSuccess: () => {
          setModalVisible(false);
        }
      });
    } catch (error) {
      // Validation failed
    }
  };

  const handleExport = async () => {
    if (selectedFields.length === 0) {
      message.warning('请至少选择一个导出的字段');
      return;
    }
    setExporting(true);
    try {
      const response = await apiClient.post(
        '/admin/members/export/',
        { fields: selectedFields },
        {
          params: {
            keyword: params.keyword,
            category_code: params.category_code
          },
          responseType: 'blob'
        }
      );
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `后台会员导出_${new Date().toLocaleDateString().replace(/\//g, '-')}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      message.success('自定义导出 Excel 成功！');
      setExportModalVisible(false);
    } catch (err) {
      console.error(err);
      message.error('导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  const handleCatSubmit = async () => {
    const values = await catForm.validateFields();
    createCategoryMutation.mutate(values, {
      onSuccess: () => {
        setCatModalVisible(false);
        catForm.resetFields();
      }
    });
  };

  const handleTabChange = (key: string) => {
    setParams({
      ...params,
      category_code: key === 'all' ? undefined : key,
      page: 1
    });
  };

  const addRoleItem = () => {
    const defaultCatId = categoryQuery.data?.[0]?.id || 1;
    setRolesList([...rolesList, { category: defaultCatId, org_name: '', position: '' }]);
  };

  const removeRoleItem = (index: number) => {
    const updated = [...rolesList];
    updated.splice(index, 1);
    setRolesList(updated);
  };

  const updateRoleItem = (index: number, field: string, value: any) => {
    const updated = [...rolesList];
    updated[index] = { ...updated[index], [field]: value };
    setRolesList(updated);
  };

  const tabItems = [
    { label: '全部会员', key: 'all' },
    ...(categoryQuery.data || []).map(cat => ({
      label: cat.name,
      key: cat.code
    }))
  ];

  const columns = [
    { 
      title: '姓名', 
      dataIndex: 'name', 
      key: 'name',
      render: (text: string) => <Text strong style={{ color: '#1677ff' }}>{text}</Text>
    },
    { 
      title: '职务与任职机构 (身兼多职)', 
      dataIndex: 'roles', 
      key: 'roles_m2m',
      render: (roles: any[]) => {
        if (!roles || roles.length === 0) return <Text type="secondary">暂无职务记录</Text>;
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {roles.map((r, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <Tag color={
                  r.category_code === 'company' ? 'blue' :
                  r.category_code === 'association' ? 'purple' :
                  r.category_code === 'office' ? 'orange' : 'cyan'
                } style={{ borderRadius: 4, margin: 0 }}>
                  {r.category_name}
                </Tag>
                <Text strong style={{ fontSize: 13, color: '#333' }}>{r.org_name}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>— {r.position || '职务暂缺'}</Text>
              </div>
            ))}
          </div>
        );
      }
    },
    { 
      title: '联系电话', 
      dataIndex: 'phone', 
      key: 'phone',
      render: (text: string) => <span style={{ fontFamily: 'Courier New, monospace' }}>{text}</span>
    },
    { 
      title: '会员状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'success' : 'error'} style={{ borderRadius: 4 }}>
          {status === 'active' ? '活跃' : '冻结'}
        </Tag>
      )
    },
    {
      title: '采集入库时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm'),
    },
    { 
      title: '操作', 
      key: 'action',
      render: (_: any, record: Member) => (
        <Space size="middle">
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)}
            size="small"
            style={{ color: '#1677ff' }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要彻底删除该会员记录吗？"
            description="删除后该会员的短信群发统计和关联数据将被清空且不可恢复。"
            onConfirm={() => deleteMemberMutation.mutate(record.id)}
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              size="small"
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    },
  ];

  return (
    <div className="member-admin-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
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
          <div style={{ background: '#0b1d33', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <TeamOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#1a1a1a', fontWeight: 'bold' }}>会员管理后台</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#666' }}>进行高精会员录入、身兼多职档案建档、动态组织分类管理及全生命周期 CRUD 维护。</p>
          </div>
        </div>
        <Space>
          <Button 
            icon={<DownloadOutlined />} 
            onClick={() => setExportModalVisible(true)}
            style={{ borderRadius: 6, fontWeight: 500 }}
          >
            自定义导出 Excel
          </Button>
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleAdd}
            style={{ borderRadius: 6, fontWeight: 500, background: '#0b1d33', borderColor: '#0b1d33' }}
          >
            添加会员
          </Button>
        </Space>
      </div>

      {/* 搜索与分类 Tabs 卡片面板 */}
      <Card 
        bordered={false} 
        style={{ 
          background: '#fff', 
          borderRadius: 12, 
          marginBottom: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)',
          border: '1px solid #f0f0f0'
        }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', marginBottom: 16 }}>
          <Input.Search 
            placeholder="搜索会员姓名 / 任职机构名称 / 职务 / 手机号" 
            onSearch={handleSearch}
            value={params.keyword}
            onChange={(e) => setParams({ ...params, keyword: e.target.value })}
            style={{ maxWidth: 450 }}
            enterButton
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={handleReset}>重置</Button>
        </div>

        {/* 动态 Tabs 分类管理 */}
        <Tabs
          activeKey={params.category_code || 'all'}
          onChange={handleTabChange}
          items={tabItems}
          tabBarExtraContent={
            <Button 
              type="dashed" 
              size="middle" 
              icon={<PlusOutlined />} 
              onClick={() => setCatModalVisible(true)}
              style={{ borderRadius: 6 }}
            >
              自定义分类模块
            </Button>
          }
        />
      </Card>

      {/* 会员列表数据表格 */}
      <Table
        dataSource={memberQuery.data?.results}
        columns={columns}
        rowKey="id"
        loading={memberQuery.isLoading}
        pagination={{ showQuickJumper: true,
          current: params.page,
          pageSize: 10,
          total: memberQuery.data?.count,
          onChange: (page) => setParams({ ...params, page }),
          showTotal: (total) => `当前类目共计 ${total} 个活跃会员档案`,
          showSizeChanger: false
        }}
        bordered
        style={{ 
          background: '#fff', 
          borderRadius: 12, 
          overflow: 'hidden',
          boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
        }}
      />

      {/* 会员采集/编辑 Modal */}
      <Modal
        title={<span style={{ fontSize: 16, fontWeight: 'bold' }}>{editingMember ? '📝 编辑会员档案' : '➕ 新增采集会员'}</span>}
        open={modalVisible}
        onOk={handleSave}
        onCancel={() => setModalVisible(false)}
        confirmLoading={saveMemberMutation.isPending}
        destroyOnClose
        width={580}
        okButtonProps={{ style: { background: '#0b1d33', borderColor: '#0b1d33' } }}
      >
        <Form 
          form={form} 
          layout="vertical" 
          initialValues={{ status: 'active' }}
          style={{ marginTop: 12 }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入会员姓名' }]}>
                <Input placeholder="请输入姓名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="phone" label="手机号" rules={[{ required: true, message: '请输入联系电话' }]}>
                <Input placeholder="请输入手机号" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="status" label="会员状态" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="active">正常活跃 (Active)</Select.Option>
              <Select.Option value="frozen">冻结限制 (Frozen)</Select.Option>
            </Select>
          </Form.Item>

          {/* 核心需求：身兼多职动态多行任职模块 */}
          <div style={{ 
            marginTop: 16, 
            marginBottom: 16, 
            padding: '16px', 
            background: '#f8f9fa', 
            borderRadius: 8,
            border: '1px solid #e9ecef'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <span style={{ fontWeight: 'bold', fontSize: 13, color: '#495057' }}>🏢 任职机构与职务 (支持身兼多职)</span>
              <Button 
                type="link" 
                size="small" 
                icon={<PlusOutlined />}
                onClick={addRoleItem}
                style={{ padding: 0 }}
              >
                添加任职单位
              </Button>
            </div>

            {rolesList.map((item, idx) => (
              <Row gutter={8} align="middle" key={idx} style={{ marginBottom: 10 }}>
                <Col span={6}>
                  <Select
                    placeholder="分类"
                    value={item.category}
                    onChange={(val) => updateRoleItem(idx, 'category', val)}
                    style={{ width: '100%' }}
                  >
                    {categoryQuery.data?.map(cat => (
                      <Select.Option key={cat.id} value={cat.id}>{cat.name}</Select.Option>
                    ))}
                  </Select>
                </Col>
                <Col span={10}>
                  <Input
                    placeholder="机构/单位全称"
                    value={item.org_name}
                    onChange={(e) => updateRoleItem(idx, 'org_name', e.target.value)}
                  />
                </Col>
                <Col span={6}>
                  <Input
                    placeholder="职务(如顾问)"
                    value={item.position}
                    onChange={(e) => updateRoleItem(idx, 'position', e.target.value)}
                  />
                </Col>
                <Col span={2} style={{ textAlign: 'center' }}>
                  <Button
                    type="text"
                    danger
                    disabled={rolesList.length === 1}
                    icon={<DeleteOutlined />}
                    onClick={() => removeRoleItem(idx)}
                    size="small"
                  />
                </Col>
              </Row>
            ))}
          </div>

          <Form.Item name="notes" label="常规备注/补充说明">
            <Input.TextArea placeholder="请输入备注或补充说明..." rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 自定义分类 Modal */}
      <Modal
        title="➕ 创建自定义分类模块"
        open={catModalVisible}
        onOk={handleCatSubmit}
        onCancel={() => setCatModalVisible(false)}
        confirmLoading={createCategoryMutation.isPending}
        destroyOnClose
        okButtonProps={{ style: { background: '#0b1d33', borderColor: '#0b1d33' } }}
      >
        <Form form={catForm} layout="vertical">
          <Form.Item 
            name="name" 
            label="分类展示名称" 
            rules={[{ required: true, message: '请输入分类展示名称，如：联盟' }]}
          >
            <Input placeholder="例如：产业联盟、分会、研究院" />
          </Form.Item>
          <Form.Item 
            name="code" 
            label="英文唯一标识编码" 
            rules={[
              { required: true, message: '请输入英文分类编码，如：alliance' },
              { pattern: /^[a-zA-Z0-9_-]+$/, message: '编码只能包含英文字母、数字和下划线' }
            ]}
          >
            <Input placeholder="例如：alliance, branch, center" />
          </Form.Item>
          <Alert 
            message="自定义分类模块创建后，前后台的分类 Tab 标签页将同步实时生成，并支持在增加会员职务时随选关联。" 
            type="info" 
            showIcon 
          />
        </Form>
      </Modal>

      {/* 自定义选择导出 Modal */}
      <Modal
        title={
          <Space>
            <DownloadOutlined style={{ color: '#1677ff' }} />
            <span>自定义导出数据列选择</span>
          </Space>
        }
        open={exportModalVisible}
        onOk={handleExport}
        onCancel={() => setExportModalVisible(false)}
        okText="确认生成并下载"
        cancelText="取消"
        confirmLoading={exporting}
        destroyOnClose
        width={480}
        okButtonProps={{ 
          style: { background: '#0b1d33', borderColor: '#0b1d33' } 
        }}
      >
        <div style={{ margin: '12px 0 20px 0' }}>
          <Text type="secondary">您可以自主挑选本次导出 Excel 表格中包含的会员字段属性：</Text>
        </div>
        <div style={{ background: '#f5f5f5', padding: 20, borderRadius: 8, border: '1px solid #e8e8e8' }}>
          <Checkbox.Group 
            options={exportFields} 
            value={selectedFields} 
            onChange={(checkedValues) => setSelectedFields(checkedValues as string[])}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          />
        </div>
      </Modal>
    </div>
  );
};

export default MemberAdminPage;
