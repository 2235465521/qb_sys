import React, { useState, useEffect } from 'react';
import { Table, Button, Space, Card, Modal, Form, Input, Select, Switch, Popconfirm, Tag, message } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

interface AdminUser {
  id: number;
  username: string;
  real_name: string;
  role: string;
  role_display: string;
  is_active: boolean;
  created_at: string;
}

const UsersManagerPage: React.FC = () => {
  const [data, setData] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<AdminUser | null>(null);
  const [form] = Form.useForm();

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get<AdminUser[]>('/admin/users/', {
        params: { keyword }
      });
      // Handle array response or paginated results
      if (Array.isArray(response.data)) {
        setData(response.data);
      } else if (response.data && (response.data as any).results) {
        setData((response.data as any).results);
      } else {
        setData([]);
      }
    } catch (error) {
      console.error(error);
      message.error('获取用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [keyword]);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: AdminUser) => {
    setEditingRecord(record);
    form.setFieldsValue({
      username: record.username,
      real_name: record.real_name,
      role: record.role,
      is_active: record.is_active,
      password: '', // Keep empty unless resetting
    });
    setModalVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingRecord) {
        // Edit Mode
        const payload: any = {
          username: values.username,
          real_name: values.real_name,
          role: values.role,
          is_active: values.is_active,
        };
        if (values.password) {
          payload.password = values.password;
        }
        await apiClient.put(`/admin/users/${editingRecord.id}/`, payload);
        message.success('用户更新成功');
      } else {
        // Create Mode
        const payload: any = {
          username: values.username,
          real_name: values.real_name,
          role: values.role,
          is_active: values.is_active,
        };
        if (values.password) {
          payload.password = values.password;
        }
        await apiClient.post('/admin/users/', payload);
        message.success('新增用户成功');
      }
      setModalVisible(false);
      fetchUsers();
    } catch (error: any) {
      console.error(error);
      const errorMsg = error.response?.data?.detail || '操作失败，请检查输入';
      message.error(errorMsg);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.delete(`/admin/users/${id}/`);
      message.success('用户已删除');
      fetchUsers();
    } catch (error) {
      console.error(error);
      message.error('删除用户失败');
    }
  };

  const columns = [
    {
      title: '账号 (用户名)',
      dataIndex: 'username',
      key: 'username',
      render: (text: string) => <span style={{ fontWeight: 'bold' }}>{text}</span>,
    },
    {
      title: '真实姓名 / 称呼',
      dataIndex: 'real_name',
      key: 'real_name',
      render: (text: string) => text || '--',
    },
    {
      title: '系统权限 / 角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string, record: AdminUser) => {
        const disp = record.role_display || role;
        if (role === 'superadmin') return <Tag color="red">{disp}</Tag>;
        if (role === 'admin') return <Tag color="blue">{disp}</Tag>;
        if (role === 'operator') return <Tag color="orange">{disp}</Tag>;
        return <Tag color="green">{disp || '普通客户'}</Tag>;
      },
    },
    {
      title: '使用状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'processing' : 'error'}>{active ? '启用中' : '已禁用'}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (val: string) => val ? new Date(val).toLocaleString() : '--',
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: AdminUser) => (
        <Space>
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)} 
          >
            编辑
          </Button>
          {record.role !== 'superadmin' && (
            <Popconfirm 
              title="确定要物理删除该账户吗？" 
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="text" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <Card 
      title="系统用户管理" 
      extra={
        <Space>
          <Input
            placeholder="搜索用户名/姓名"
            prefix={<SearchOutlined />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            style={{ width: 220 }}
            allowClear
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            新增账号
          </Button>
        </Space>
      }
    >
      <Table
        dataSource={data}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ showQuickJumper: true,
          pageSize: 10,
          showTotal: (total) => `共 ${total} 位系统用户`,
        }}
      />

      <Modal
        title={editingRecord ? '修改用户信息' : '新增系统用户'}
        open={modalVisible}
        onOk={handleOk}
        onCancel={() => setModalVisible(false)}
        width={500}
        destroyOnClose
      >
        <Form 
          form={form} 
          layout="vertical" 
          initialValues={{ is_active: true, role: 'client' }}
        >
          <Form.Item 
            name="username" 
            label="账号登录名" 
            rules={[
              { required: true, message: '请输入登录账号' },
              { min: 2, message: '账号长度至少2位' }
            ]}
          >
            <Input placeholder="支持纯字母、纯数字、字母+数字" disabled={!!editingRecord} />
          </Form.Item>

          <Form.Item 
            name="real_name" 
            label="真实姓名 / 企业称呼"
            rules={[{ required: true, message: '请输入真实姓名或称呼' }]}
          >
            <Input placeholder="如: 张三" />
          </Form.Item>

          <Form.Item 
            name="role" 
            label="系统角色权限 (支持在此将普通用户升为管理员)"
            rules={[{ required: true, message: '请选择角色类型' }]}
          >
            <Select>
              <Select.Option value="admin">管理员 (admin)</Select.Option>
              <Select.Option value="operator">内部操作员 (operator)</Select.Option>
              <Select.Option value="client">外部普通客户 (client)</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item 
            name="password" 
            label={editingRecord ? '重置密码 (留空则不修改)' : '账号登录密码 (留空则默认为 zkbz2026)'} 
            rules={[
              { min: 2, message: '密码长度至少为2位' }
            ]}
          >
            <Input.Password placeholder="密码位数2位起，支持数字/英文/混合" />
          </Form.Item>

          <Form.Item name="is_active" label="是否启用该账号" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default UsersManagerPage;
