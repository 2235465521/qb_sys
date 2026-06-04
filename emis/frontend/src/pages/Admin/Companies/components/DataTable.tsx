import React from 'react';
import { Table, Tag, Space, Button, Popconfirm, Tooltip, Spin } from 'antd';
import { EditOutlined, DeleteOutlined, EnvironmentOutlined, EyeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { Company } from '@/types';
import { useSearchData } from '@/hooks/useSearchData';

interface DataTableProps {
  data: Company[];
  loading: boolean;
  pagination: any;
  selectedRowKeys: number[];
  onSelectionChange: (keys: number[]) => void;
  onEdit: (record: Company) => void;
  onViewDetails: (record: Company) => void;
  onDelete: (id: number) => void;
  onChange: (pagination: any) => void;
}

// 嵌套展开组件：异步加载显示当前企业关联的所有标准
const ExpandedStandardList: React.FC<{ companyId: number }> = ({ companyId }) => {
  const { useCompanyStandards } = useSearchData();
  const { data: standards, isLoading } = useCompanyStandards(companyId);

  if (isLoading) {
    return (
      <div style={{ padding: '16px 0', textAlign: 'center', background: '#fafafa' }}>
        <Spin tip="正在加载关联标准目录..." size="small" />
      </div>
    );
  }

  const columns = [
    {
      title: '标准号',
      dataIndex: 'standard_no',
      key: 'standard_no',
      width: 250,
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft">
          <span 
            style={{ 
              fontWeight: 'bold', 
              color: '#13c2c2',
              display: 'block',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            {text}
          </span>
        </Tooltip>
      ),
    },
    {
      title: '标准名称',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '标准分类',
      dataIndex: 'type_display',
      key: 'type_display',
      width: 120,
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status_display',
      key: 'status_display',
      width: 100,
      render: (text: string, record: any) => (
        <Tag color={record.status === 'active' ? 'success' : 'default'}>{text}</Tag>
      ),
    },
  ];

  return (
    <div style={{ padding: '12px 24px', background: '#fcfcfc', borderRadius: 8, border: '1px dashed #e8e8e8' }}>
      <h4 style={{ marginTop: 0, marginBottom: 8, color: '#666' }}>关联标准目录</h4>
      <Table
        columns={columns}
        dataSource={standards || []}
        rowKey="id"
        pagination={false}
        size="small"
        locale={{ emptyText: '该企业暂未关联任何标准目录' }}
      />
    </div>
  );
};

const DataTable: React.FC<DataTableProps> = ({
  data,
  loading,
  pagination,
  selectedRowKeys,
  onSelectionChange,
  onEdit,
  onViewDetails,
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
      render: (val) => val ? val.split('T')[0] : '',
    },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 150,
      render: (_, record) => (
        <Space size="small">
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined style={{ color: '#1890ff' }} />}
              onClick={() => onViewDetails(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined style={{ color: '#fa8c16' }} />}
              onClick={() => onEdit(record)}
            />
          </Tooltip>
          <Tooltip title="删除">
            <Popconfirm
              title="确定要删除该企业吗？"
              onConfirm={() => onDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  // 配置行勾选
  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => {
      onSelectionChange(keys as number[]);
    },
  };

  return (
    <Table
      rowSelection={rowSelection}
      columns={columns}
      dataSource={data}
      rowKey="id"
      loading={loading}
      pagination={{ 
        showQuickJumper: true,
        ...pagination,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条数据`,
      }}
      onChange={onChange}
      scroll={{ x: 1200 }}
      expandable={{
        expandedRowRender: (record) => <ExpandedStandardList companyId={record.id} />,
        rowExpandable: () => true,
      }}
    />
  );
};

export default DataTable;
