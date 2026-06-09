import React, { useState } from 'react';
import { Table, Button, Space, Card, Modal, Form, Input, Switch, Popconfirm, Tag, Typography, Tooltip } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { useSmsData } from '@/hooks/useSmsData';
import type { SmsTemplate } from '@/types';
import ErrorBoundary from '@/components/ErrorBoundary';

const { Text } = Typography;

const SmsTemplatesPage: React.FC = () => {
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<SmsTemplate | null>(null);
  const [form] = Form.useForm();

  const { templateQuery, saveMutation, deleteMutation } = useSmsData();

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: SmsTemplate) => {
    setEditingRecord(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleOk = async () => {
    const values = await form.validateFields();
    saveMutation.mutate({ ...editingRecord, ...values }, {
      onSuccess: () => setModalVisible(false),
    });
  };

  const columns = [
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
    },
    {
      title: '短信内容',
      dataIndex: 'content',
      key: 'content',
      ellipsis: { showTitle: false },
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft" color="rgba(0,0,0,0.85)">
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{text}</span>
        </Tooltip>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Tag color={active ? 'blue' : 'default'}>{active ? '启用' : '禁用'}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (val: string) => new Date(val).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: SmsTemplate) => (
        <Space>
          <Button type="text" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
          <Popconfirm title="确定删除吗？" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card title="短信模板管理" extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增模板</Button>}>
      <Table
        dataSource={Array.isArray(templateQuery.data) ? templateQuery.data : []}
        columns={columns}
        rowKey="id"
        loading={templateQuery.isLoading}
      />

      <Modal
        title={editingRecord ? '编辑模板' : '新增模板'}
        open={modalVisible}
        onOk={handleOk}
        onCancel={() => setModalVisible(false)}
        confirmLoading={saveMutation.isPending}
        width={600}
        destroyOnClose
      >
        <Form form={form} layout="vertical" initialValues={{ is_active: true }}>
          <Form.Item name="name" label="模板名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如: 标准到期提醒" />
          </Form.Item>
          <Form.Item 
            name="content" 
            label="模板内容" 
            rules={[{ required: true, message: '请输入内容' }]}
            help={
              <Space direction="vertical" size={0}>
                <Text type="secondary"><InfoCircleOutlined /> 支持变量: </Text>
                <Text code>{'{name}'}</Text> - 会员姓名
                <Text code>{'{company}'}</Text> - 所在企业
              </Space>
            }
          >
            <Input.TextArea rows={4} placeholder="如: 尊敬的{name}，您好！您公司的标准即将到期..." />
          </Form.Item>
          <Form.Item name="is_active" label="是否启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default function SmsTemplatesPageWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <SmsTemplatesPage />
    </ErrorBoundary>
  );
}
