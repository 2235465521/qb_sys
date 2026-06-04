import React from 'react';
import { Table, Tag, Button, Space, Popconfirm, Tooltip } from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import type { Standard } from '@/types';
import dayjs from 'dayjs';

interface DataTableProps {
  data: Standard[];
  loading: boolean;
  pagination: any;
  onEdit: (record: Standard) => void;
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
  const columns = [
    {
      title: '标准编号',
      dataIndex: 'standard_no',
      key: 'standard_no',
      width: 170,
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft">
          <span 
            style={{ 
              fontWeight: 'bold', 
              fontFamily: 'Courier New, monospace',
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
      width: 300,
      ellipsis: true,
      render: (text: string) => <span title={text} style={{ fontWeight: 500 }}>{text || '--'}</span>,
    },
    {
      title: '起草单位/企业名称',
      dataIndex: 'company_name',
      key: 'company_name',
      width: 240,
      ellipsis: true,
      render: (text: string) => text ? <Tag color="blue" title={text} style={{ borderRadius: 4, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>{text}</Tag> : '--',
    },
    {
      title: '标准状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      align: 'center' as const,
      render: (status: string, record: any) => {
        if (status === 'active') {
          return <Tag color="success" style={{ borderRadius: 4 }}>{record.status_display || '现行'}</Tag>;
        }
        if (status === 'deprecated') {
          return <Tag color="error" style={{ borderRadius: 4 }}>{record.status_display || '已废止'}</Tag>;
        }
        return <Tag color="warning" style={{ borderRadius: 4 }}>{record.status_display || '草案'}</Tag>;
      },
    },
    {
      title: '发布时间',
      dataIndex: 'publish_date',
      key: 'publish_date',
      width: 120,
      align: 'center' as const,
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD') : '--',
    },
    {
      title: '实施时间',
      dataIndex: 'implement_date',
      key: 'implement_date',
      width: 120,
      align: 'center' as const,
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD') : '--',
    },
    {
      title: '同步入库时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      align: 'center' as const,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: 170,
      align: 'center' as const,
      fixed: 'right' as const,
      render: (_: any, record: Standard) => (
        <Space size="middle" style={{ paddingRight: 8 }}>
          <Button 
            type="text" 
            icon={<EditOutlined />} 
            onClick={() => onEdit(record)}
            size="small"
          >
            修改
          </Button>
          <Popconfirm
            title="确定要物理删除该企标资产吗？"
            description="删除后此企标及其PDF绑定关系将彻底消失且不可恢复。"
            onConfirm={() => onDelete(record.id)}
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
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="id"
      loading={loading}
      scroll={{ x: 1370 }}
      pagination={{ showQuickJumper: true,
        ...pagination,
        showSizeChanger: false,
        showTotal: (total) => `共计 ${total} 条标准资产`,
      }}
      onChange={onChange}
      bordered
      style={{ 
        background: '#fff', 
        borderRadius: 12, 
        overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
      }}
    />
  );
};

export default DataTable;
