import React, { useState } from 'react';
import { Modal, Upload, message, Typography, Button, Table, Alert } from 'antd';
import { InboxOutlined, DownloadOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Dragger } = Upload;
const { Text } = Typography;

interface ImportReferencesModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

interface ValidationError {
  row: number;
  error: string;
}

interface ImportResult {
  success_count: number;
  errors: ValidationError[];
}

const ImportReferencesModal: React.FC<ImportReferencesModalProps> = ({ open, onCancel, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);

  // 下载规范模板函数
  const handleDownloadTemplate = async () => {
    try {
      const response = await apiClient.get('/admin/standards/import-references/template/', {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', '企标规范性引用导入模板.xlsx');
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      message.success('下载导入模板成功！');
    } catch (err) {
      console.error(err);
      message.error('下载模板失败，请稍后重试');
    }
  };

  // 处理拖拽上传文件
  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setResult(null);
    try {
      const { data } = await apiClient.post<ImportResult>('/admin/standards/import-references/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      if (data.success_count > 0 && data.errors.length === 0) {
        message.success(`导入成功！共新增引用关联关系 ${data.success_count} 条`);
        onSuccess();
      } else if (data.success_count > 0 && data.errors.length > 0) {
        message.warning(`部分关联成功（${data.success_count} 条），但仍有 ${data.errors.length} 行记录校验失败。`);
        onSuccess();
      } else if (data.success_count === 0 && data.errors.length > 0) {
        message.error(`导入未完成！上传数据全部存在校验错误（共 ${data.errors.length} 项）。`);
      }
    } catch (error: any) {
      const errMsg = error?.response?.data?.error || '导入解析失败，请检查文件模版';
      message.error(errMsg);
    } finally {
      setUploading(false);
    }
    return false; // 阻止 Antd 默认自动上传行为
  };

  const reset = () => {
    setResult(null);
    onCancel();
  };

  // 报错报告数据列
  const columns = [
    {
      title: 'Excel 行号',
      dataIndex: 'row',
      key: 'row',
      width: 120,
      align: 'center' as const,
      render: (row: number) => (
        <span style={{ fontWeight: 'bold', color: '#ff4d4f' }}>
          第 {row} 行
        </span>
      )
    },
    {
      title: '冲突或格式错误原因说明',
      dataIndex: 'error',
      key: 'error',
      render: (text: string) => (
        <Text type="danger" style={{ fontSize: 13, fontWeight: 500 }}>
          {text}
        </Text>
      )
    }
  ];

  return (
    <Modal
      title={<span style={{ fontSize: 18, fontWeight: 'bold' }}>导入企标规范性引用目录</span>}
      open={open}
      onCancel={reset}
      footer={null}
      width={700}
      destroyOnClose
    >
      <div style={{ marginBottom: 20 }}>
        <Text type="secondary" style={{ display: 'block', lineHeight: '1.6', marginBottom: 12 }}>
          请点击下载最新规范模板，按要求填写企标与引用的标准编码映射。
          系统会对「企标存在性」、「唯一冲突」等进行严格的一致性筛查，只入库通过校验的数据。
        </Text>
        
        <Button
          type="primary"
          ghost
          icon={<DownloadOutlined />}
          onClick={handleDownloadTemplate}
          style={{ borderRadius: 6 }}
        >
          下载导入模板 (.xlsx)
        </Button>
      </div>

      <Dragger
        accept=".xlsx,.xls"
        multiple={false}
        beforeUpload={handleUpload}
        showUploadList={false}
        disabled={uploading}
        style={{ background: '#fafafa', borderRadius: 12, padding: '24px 0' }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text" style={{ fontWeight: 500 }}>点击或将规范性引用的 Excel 文件拖拽到此区域上传</p>
        <p className="ant-upload-hint" style={{ fontSize: 12 }}>
          {uploading ? '系统正在高速读取引用目录并对齐关联关系中...' : '支持 .xlsx 或 .xls 格式，仅包含企标与引用的国行标列表'}
        </p>
      </Dragger>

      {/* 纠错反馈 UI */}
      {result && (
        <div style={{ marginTop: 24 }}>
          {result.success_count > 0 && (
            <Alert
              message={`成功入库提示`}
              description={`本次操作已成功将 ${result.success_count} 条无误的企标规范性引用目录写入数据库。`}
              type="success"
              showIcon
              style={{ marginBottom: 16, borderRadius: 8 }}
            />
          )}

          {result.errors && result.errors.length > 0 && (
            <div>
              <Alert
                message={`导入中发现 ${result.errors.length} 项数据异常`}
                description="以下是后端接口在解析过程中拦截的数据报错列表。请针对行号核实并修改 Excel，然后重新导入异常的记录。"
                type="error"
                showIcon
                style={{ marginBottom: 16, borderRadius: 8 }}
              />
              <Table
                columns={columns}
                dataSource={result.errors.map((err, idx) => ({ ...err, key: idx }))}
                size="small"
                bordered
                pagination={{ pageSize: 5, showSizeChanger: false }}
                style={{ borderRadius: 8, overflow: 'hidden' }}
              />
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};

export default ImportReferencesModal;
