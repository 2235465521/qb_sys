import React from 'react';
import { Table, Tag, Space, Button, Popconfirm, Tooltip } from 'antd';
import { EditOutlined, DeleteOutlined, EnvironmentOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { Company } from '@/types';

interface DataTableProps {
  data: Company[];
  loading: boolean;
  pagination: any;
  onEdit: (record: Company) => void;
  onDelete: (id: number) => void;
  onChange: (pagination: any) => void;
}

const DataTable: React.FC<DataTableProps> = ({
  data,
  loading,
  pagination,
  onEdit,
  onDelete,
  onChange,
}) => {
  const columns: ColumnsType<Company> = [
    {
      title: '企业名称',
      dataIndex: 'name',
      key: 'name',
      ellipsis: true,
    },
    {
      title: '信用代码',
      dataIndex: 'credit_code',
      key: 'credit_code',
      width: 200,
    },
    {
      title: '法人',
      dataIndex: 'legal_person',
      key: 'legal_person',
      width: 100,
    },
    {
      title: '所属区域',
      key: 'region',
      width: 200,
      render: (_, record) => (
        <span>
          {record.province_name} {record.city_name} {record.district_name}
        </span>
      ),
    },
    {
      title: '坐标',
      key: 'coords',
      width: 80,
      align: 'center',
      render: (_, record) => (
        record.latitude ? (
          <Tooltip title={`Lat: ${record.latitude}, Lng: ${record.longitude}`}>
            <EnvironmentOutlined style={{ color: '#52c41a' }} />
          </Tooltip>
        ) : <EnvironmentOutlined style={{ color: '#bfbfbf' }} />
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '正常' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '入库时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (val) => val.split('T')[0],
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 120,
      render: (_, record) => (
        <Space size="middle">
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => onEdit(record)}
          />
          <Popconfirm
            title="确定要删除该企业吗？"
            onConfirm={() => onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="id"
      loading={loading}
      pagination={{ showQuickJumper: true,
        ...pagination,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条数据`,
      }}
      onChange={onChange}
      scroll={{ x: 1200 }}
    />
  );
};

export default DataTable;
