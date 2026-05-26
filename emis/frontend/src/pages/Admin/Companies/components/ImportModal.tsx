import React, { useState } from 'react';
import { Modal, Upload, message, Button, Space, Typography, List } from 'antd';
import { InboxOutlined, DownloadOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Dragger } = Upload;
const { Text } = Typography;

interface ImportModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

const ImportModal: React.FC<ImportModalProps> = ({ open, onCancel, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    try {
      const { data } = await apiClient.post('/admin/companies/import/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      if (data.success > 0) {
        message.success(`成功导入 ${data.success} 条数据`);
        onSuccess();
      } else if (data.errors.length === 0) {
        message.warning('没有新数据被导入');
      }
    } catch (error) {
      message.error('导入失败，请检查文件格式');
    } finally {
      setUploading(false);
    }
    return false; // Prevent auto upload
  };

  const reset = () => {
    setResult(null);
    onCancel();
  };

  return (
    <Modal
      title="批量导入企业"
      open={open}
      onCancel={reset}
      footer={null}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">
          请下载模板并按格式填写数据后上传。支持 .xlsx, .xls 格式。
        </Text>
        <div style={{ marginTop: 8 }}>
          <Button 
            type="link" 
            icon={<DownloadOutlined />} 
            size="small"
            onClick={() => window.location.href = '/api/admin/companies/import/template/'}
          >
            下载导入模板.xlsx
          </Button>
        </div>
      </div>

      <Dragger
        accept=".xlsx,.xls"
        multiple={false}
        beforeUpload={handleUpload}
        showUploadList={false}
        disabled={uploading}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或将文件拖拽到此区域上传</p>
        <p className="ant-upload-hint">
          {uploading ? '正在解析并导入，请稍候...' : '支持单个文件上传，严禁上传非业务相关数据'}
        </p>
      </Dragger>

      {result && (
        <div style={{ marginTop: 24 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text strong>导入结果：</Text>
            <Text>成功：<Text type="success">{result.success}</Text></Text>
            <Text>跳过（重复）：<Text type="warning">{result.skipped}</Text></Text>
            {result.errors.length > 0 && (
              <>
                <Text type="danger">错误详情：</Text>
                <List
                  size="small"
                  bordered
                  dataSource={result.errors}
                  renderItem={(item: string) => <List.Item><Text type="danger" style={{ fontSize: 12 }}>{item}</Text></List.Item>}
                  style={{ maxHeight: 200, overflow: 'auto' }}
                />
              </>
            )}
          </Space>
        </div>
      )}
    </Modal>
  );
};

export default ImportModal;
