import React, { useState } from 'react';
import { Table, Tag, Button, Space, message, Modal, Row, Col, Card, Empty, Tooltip } from 'antd';
import { DownloadOutlined, EyeOutlined, FileExcelOutlined } from '@ant-design/icons';
import type { Standard } from '@/types';
import dayjs from 'dayjs';
import apiClient from '@/api/client';

interface StandardsTableProps {
  data: Standard[];
  loading: boolean;
  selectedRowKeys: React.Key[];
  onSelectionChange: (keys: React.Key[]) => void;
}

const StandardsTable: React.FC<StandardsTableProps> = ({
  data,
  loading,
  selectedRowKeys,
  onSelectionChange,
}) => {
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState('');

  const formatUrlForSafety = (url: string) => {
    if (!url) return '';
    if (url.startsWith('/')) {
      return url;
    }
    if (window.location.protocol === 'https:' && url.startsWith('http://')) {
      return url.replace(/^http:\/\//i, 'https://');
    }
    return url;
  };

  const appendQueryParam = (url: string, key: string, value: string) => {
    if (!url) return '';
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}${key}=${value}`;
  };

  const handleDownload = (record: Standard) => {
    if (record.pdf_url) {
      const downloadUrl = appendQueryParam(record.pdf_url, 'mode', 'download');
      const safeUrl = formatUrlForSafety(downloadUrl);
      
      const link = document.createElement('a');
      link.href = safeUrl;
      link.setAttribute('download', `${record.standard_no}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
      message.success(`开始下载: ${record.standard_no}`);
    } else {
      message.warning('该标准暂未上传关联 PDF 文件');
    }
  };

  const handlePreview = (record: Standard) => {
    if (record.pdf_url) {
      const previewUrl = appendQueryParam(record.pdf_url, 'mode', 'preview');
      setPreviewTitle(record.standard_no);
      setPreviewUrl(formatUrlForSafety(previewUrl));
      setPreviewVisible(true);
    } else {
      message.warning('该标准暂未上传关联 PDF 文件');
    }
  };

  const handleExportReferences = async (record: Standard) => {
    try {
      const response = await apiClient.get(`/client/standards/${record.id}/export-references/`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${record.standard_no}_规范性引用标准.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(downloadUrl);
      message.success(`导出引用目录成功: ${record.standard_no}`);
    } catch (err) {
      message.error('导出引用目录失败，请稍后重试');
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
      dataIndex: 'publish_date',
      key: 'publish_date',
      render: (date: string) => date ? dayjs(date).format('YYYY-MM-DD') : '--',
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      fixed: 'right' as const,
      render: (_: any, record: Standard) => (
        <Space size="middle">
          <Tooltip title={record.pdf_url ? '预览' : '无文件可预览'}>
            <Button
              type="text"
              icon={<EyeOutlined />}
              disabled={!record.pdf_url}
              onClick={() => handlePreview(record)}
              style={{ color: record.pdf_url ? '#1677ff' : undefined }}
            />
          </Tooltip>
          <Tooltip title={record.pdf_url ? '下载' : '无文件可下载'}>
            <Button
              type="text"
              icon={<DownloadOutlined />}
              disabled={!record.pdf_url}
              onClick={() => handleDownload(record)}
              style={{ color: record.pdf_url ? '#52c41a' : undefined }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const expandedRowRender = (record: Standard) => {
    const subColumns = [
      {
        title: '序号',
        key: 'index',
        width: 80,
        render: (_: any, __: any, index: number) => index + 1
      },
      {
        title: '被引用标准号',
        dataIndex: 'cited_standard_no',
        key: 'cited_standard_no',
        render: (text: string) => (
          <span style={{ fontFamily: 'Courier New, monospace', fontWeight: 500 }}>
            {text}
          </span>
        )
      },
      {
        title: '最新标准号',
        dataIndex: 'latest_standard_no',
        key: 'latest_standard_no',
        render: (text: string) => text ? (
          <span style={{ fontFamily: 'Courier New, monospace', color: '#8c8c8c' }}>
            {text}
          </span>
        ) : (
          <span style={{ color: '#bfbfbf', fontSize: 12 }}>暂无最新标准</span>
        )
      }
    ];

    const refData = record.normative_references || [];

    return (
      <div style={{ padding: '12px 16px', background: '#f5f7fa', borderRadius: 8 }}>
        <Row gutter={24}>
          <Col span={14}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h4 style={{ margin: 0, color: '#006064', fontSize: 14, fontWeight: 'bold' }}>
                规范性引用标准目录 ({refData.length})
              </h4>
              <Button
                type="primary"
                ghost
                size="small"
                icon={<FileExcelOutlined />}
                disabled={refData.length === 0}
                onClick={() => handleExportReferences(record)}
                style={{ borderRadius: 4 }}
              >
                导出引用目录 (Excel)
              </Button>
            </div>
            <Table
              columns={subColumns}
              dataSource={refData}
              rowKey="id"
              pagination={false}
              size="small"
              bordered
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该标准暂无规范性引用标准数据" /> }}
            />
          </Col>
          <Col span={10}>
            <Card
              title={<span style={{ color: '#006064', fontSize: 14, fontWeight: 'bold' }}>详细指标查看</span>}
              size="small"
              bordered
              style={{ height: '100%', borderRadius: 8, background: '#fff' }}
            >
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="指标深度解析与查看功能正在研发中，敬请期待..."
                style={{ margin: '20px 0' }}
              />
            </Card>
          </Col>
        </Row>
      </div>
    );
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => {
      onSelectionChange(keys);
    },
  };

  return (
    <>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        pagination={false}
        bordered
        rowSelection={rowSelection}
        expandable={{
          expandedRowRender,
          rowExpandable: () => true,
        }}
        style={{
          background: '#fff',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.02)'
        }}
      />

      {/* 预览弹窗 Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#006064', fontWeight: 'bold', fontSize: 16 }}>
            <EyeOutlined />
            <span>标准在线预览 ({previewTitle})</span>
          </div>
        }
        open={previewVisible}
        onCancel={() => {
          setPreviewVisible(false);
          setPreviewUrl(null);
          setPreviewTitle('');
        }}
        footer={null}
        width="80%"
        style={{ top: 40 }}
        bodyStyle={{ height: 'calc(100vh - 160px)', padding: 0 }}
        destroyOnClose
        centered
      >
        {previewUrl ? (
          <iframe
            src={previewUrl}
            width="100%"
            height="100%"
            style={{ border: 'none', borderRadius: '0 0 8px 8px' }}
            title="PDF Preview"
          />
        ) : (
          <div style={{ padding: 48, textAlign: 'center' }}>
            正在加载预览内容...
          </div>
        )}
      </Modal>
    </>
  );
};

export default StandardsTable;
