import React from 'react';
import { Table, Tag, Button, Space, message } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { Standard } from '@/types';
import dayjs from 'dayjs';

interface StandardsTableProps {
  data: Standard[];
  loading: boolean;
}

const StandardsTable: React.FC<StandardsTableProps> = ({
  data,
  loading,
}) => {
  const handleDownload = (record: Standard) => {
    if (record.pdf_url) {
      window.open(record.pdf_url, '_blank');
      message.success(`开始下载: ${record.standard_no}`);
    } else {
      message.warning('该标准暂未上传关联 PDF 文件');
    }
  };

  const columns = [
    {
      title: '标准编号',
      dataIndex: 'standard_no',
      key: 'standard_no',
      render: (text: string) => (
        <span style={{ fontWeight: 'bold', color: '#1677ff', fontFamily: 'Courier New, monospace' }}>
          {text}
        </span>
      ),
    },
    {
      title: '标准名称',
      dataIndex: 'title',
      key: 'title',
      width: '35%',
      ellipsis: true,
      render: (text: string) => <span title={text} style={{ fontWeight: 500 }}>{text || '--'}</span>,
    },
    {
      title: '起草单位 / 企业名称',
      dataIndex: 'company_name',
      key: 'company_name',
      ellipsis: true,
      render: (text: string) => text ? <Tag color="blue" title={text} style={{ borderRadius: 4, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>{text}</Tag> : '--',
    },
    {
      title: '标准状态',
      dataIndex: 'status',
      key: 'status',
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
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Standard) => (
        <Space size="middle">
          <Button
            type="primary"
            ghost
            icon={<DownloadOutlined />}
            size="small"
            disabled={!record.pdf_url}
            onClick={() => handleDownload(record)}
            style={{ borderRadius: 4 }}
          >
            下载标准
          </Button>
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
      pagination={false}
      bordered
      style={{
        background: '#fff',
        borderRadius: 12,
        overflow: 'hidden',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.02)'
      }}
    />
  );
};

export default StandardsTable;
