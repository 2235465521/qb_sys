import React, { useState, useEffect } from 'react';
import { Table, Tag, Button, Space, message, Modal, Empty, Tooltip, Drawer, Typography } from 'antd';
import { DownloadOutlined, EyeOutlined, FileExcelOutlined } from '@ant-design/icons';
import type { Standard } from '@/types';
import dayjs from 'dayjs';
import apiClient from '@/api/client';

interface StandardsTableProps {
  data: Standard[];
  loading: boolean;
  selectedRowKeys: React.Key[];
  onSelectionChange: (keys: React.Key[]) => void;
  keyword?: string;
  searchMode?: 'title' | 'full_text';
}

const StandardsTable: React.FC<StandardsTableProps> = ({
  data,
  loading,
  selectedRowKeys,
  onSelectionChange,
  keyword,
  searchMode,
}) => {
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState('');
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedStandard, setSelectedStandard] = useState<Standard | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);

  useEffect(() => {
    if (searchMode === 'full_text' && keyword && data) {
      const keysWithSnippet = data.filter(item => !!item.snippet).map(item => item.id);
      setExpandedKeys(keysWithSnippet);
    } else {
      setExpandedKeys([]);
    }
  }, [data, searchMode, keyword]);

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
      let previewUrl = appendQueryParam(record.pdf_url, 'mode', 'preview');
      if (searchMode === 'full_text' && keyword) {
        // 传递 ?search=keyword 给预览器以支持后端提取定位，同时加上原生 #search 锚点
        previewUrl = appendQueryParam(previewUrl, 'search', keyword);
        previewUrl = `${previewUrl}#search=${encodeURIComponent(keyword)}`;
      }
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
    } catch (err: any) {
      const responseData = err.response?.data;
      if (responseData instanceof Blob) {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const errorData = JSON.parse(reader.result as string);
            message.error(errorData.detail || '导出引用目录失败，请稍后重试');
          } catch (e) {
            message.error('导出引用目录失败，请稍后重试');
          }
        };
        reader.readAsText(responseData);
      } else if (responseData && typeof responseData === 'object' && responseData.detail) {
        message.error(responseData.detail);
      } else {
        message.error('导出引用目录失败，请稍后重试');
      }
    }
  };

  const columns = [
    {
      title: '标准编号',
      dataIndex: 'standard_no',
      key: 'standard_no',
      width: 160,
      render: (text: string, record: Standard) => (
        <Typography.Link
          style={{ fontWeight: 'bold', fontFamily: 'Courier New, monospace' }}
          onClick={() => {
            setSelectedStandard(record);
            setDrawerVisible(true);
          }}
        >
          {text}
        </Typography.Link>
      ),
    },
    {
      title: '企业名称',
      dataIndex: 'company_name',
      key: 'company_name',
      width: '25%',
      ellipsis: true,
      render: (text: string) => text ? <Tag color="blue" title={text} style={{ borderRadius: 4, maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>{text}</Tag> : '--',
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
      <div style={{ padding: '16px 20px', background: '#f8fafc', borderRadius: 8 }}>
        {record.snippet && (
          <div style={{
            marginBottom: 16,
            padding: '12px 16px',
            background: '#fff',
            borderLeft: '4px solid #00bcd4',
            borderRadius: '0 8px 8px 0',
            boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
          }}>
            <h4 style={{ margin: '0 0 6px 0', color: '#00838f', fontSize: 13, fontWeight: 'bold' }}>全文检索匹配摘要：</h4>
            <div
              style={{ fontSize: 14, color: '#333', lineHeight: '1.6' }}
              dangerouslySetInnerHTML={{ __html: record.snippet }}
            />
          </div>
        )}
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
          expandedRowKeys: expandedKeys,
          onExpandedRowsChange: (keys) => setExpandedKeys(keys as React.Key[]),
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

      {/* 详细指标 Drawer */}
      <Drawer
        title={
          <span style={{ color: '#006064', fontWeight: 'bold', fontSize: 16 }}>
            详细指标 - {selectedStandard?.standard_no || ''}
          </span>
        }
        placement="right"
        width={600}
        onClose={() => {
          setDrawerVisible(false);
          setSelectedStandard(null);
        }}
        open={drawerVisible}
        destroyOnClose
      >
        <div style={{ 
          height: '100%', 
          display: 'flex', 
          flexDirection: 'column', 
          justifyContent: 'center', 
          alignItems: 'center',
          padding: 24
        }}>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="指标深度解析与查看功能正在研发中，敬请期待..."
            style={{ margin: '20px 0' }}
          />
        </div>
      </Drawer>
    </>
  );
};

export default StandardsTable;
