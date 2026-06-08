import React, { useState, useEffect, useRef } from 'react';
import { Modal, Upload, message, Button, Space, Typography, List, Progress } from 'antd';
import { InboxOutlined, DownloadOutlined, CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Dragger } = Upload;
const { Text } = Typography;

interface ImportModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

interface ImportStatus {
  status: 'queued' | 'processing' | 'done' | 'failed';
  progress: number;
  success: number;
  skipped: number;
  errors: string[];
  total: number;
}

const ImportModal: React.FC<ImportModalProps> = ({ open, onCancel, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const pollingIntervalRef = useRef<number | null>(null);

  const startPolling = (id: string) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const { data } = await apiClient.get(`/admin/companies/import/status/${id}/`);
        setImportStatus(data);

        if (data.status === 'done' || data.status === 'failed') {
          clearInterval(pollingIntervalRef.current!);
          setUploading(false);
          if (data.status === 'done') {
            message.success(`导入完成，成功 ${data.success} 条`);
            onSuccess();
          } else {
            message.error('导入失败');
          }
        }
      } catch (error) {
        console.error('查询导入状态失败', error);
        clearInterval(pollingIntervalRef.current!);
        setUploading(false);
        message.error('查询导入状态失败');
      }
    }, 2000);
  };

  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setTaskId(null);
    setImportStatus(null);
    try {
      const { data } = await apiClient.post('/admin/companies/import/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5分钟，应对超大文件上传
      });
      if (data.task_id) {
        setTaskId(data.task_id);
        startPolling(data.task_id);
      } else {
        message.error('获取任务ID失败');
        setUploading(false);
      }
    } catch (error) {
      message.error('上传失败，请检查文件格式或网络');
      setUploading(false);
    }
    return false; // Prevent auto upload
  };

  const handleDownloadTemplate = async () => {
    try {
      const response = await apiClient.get('/admin/companies/import/template/', {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', '企业批量导入模板.xlsx');
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

  const reset = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    setUploading(false);
    setTaskId(null);
    setImportStatus(null);
    onCancel();
  };

  return (
    <Modal
      title="批量导入企业"
      open={open}
      onCancel={reset}
      footer={null}
      destroyOnClose
      maskClosable={!uploading}
      closable={!uploading}
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">
          请下载模板并按格式填写数据后上传。支持大批量导入（5万条+），导入在后台异步执行。
        </Text>
        <div style={{ marginTop: 8 }}>
          <Button 
            type="link" 
            icon={<DownloadOutlined />} 
            size="small"
            onClick={handleDownloadTemplate}
          >
            下载导入模板.xlsx
          </Button>
        </div>
      </div>

      {!taskId && (
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
            支持极大文件上传（超过5万条），由于异步处理，您可以关闭页面稍后查看。
          </p>
        </Dragger>
      )}

      {importStatus && (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            <div>
              {importStatus.status === 'queued' && <><SyncOutlined spin /> <Text>排队中，等待后台处理...</Text></>}
              {importStatus.status === 'processing' && <><SyncOutlined spin /> <Text>正在解析并入库...</Text></>}
              {importStatus.status === 'done' && <><CheckCircleOutlined style={{color: '#52c41a'}}/> <Text type="success">处理完成</Text></>}
              {importStatus.status === 'failed' && <><CloseCircleOutlined style={{color: '#f5222d'}}/> <Text type="danger">处理失败</Text></>}
            </div>

            <Progress percent={importStatus.progress} status={importStatus.status === 'failed' ? 'exception' : 'active'} />
            
            <Space size="large">
               <Text>成功：<Text type="success" strong>{importStatus.success}</Text></Text>
               <Text>跳过（重复）：<Text type="warning" strong>{importStatus.skipped}</Text></Text>
               <Text>总数：<Text strong>{importStatus.total}</Text></Text>
            </Space>

            {importStatus.errors && importStatus.errors.length > 0 && (
              <div style={{ textAlign: 'left', marginTop: 16 }}>
                <Text type="danger" strong>部分错误详情（最多显示前100条）：</Text>
                <List
                  size="small"
                  bordered
                  dataSource={importStatus.errors}
                  renderItem={(item: string) => <List.Item><Text type="danger" style={{ fontSize: 12 }}>{item}</Text></List.Item>}
                  style={{ maxHeight: 200, overflow: 'auto', marginTop: 8 }}
                />
              </div>
            )}
            
            {(importStatus.status === 'done' || importStatus.status === 'failed') && (
                <Button type="primary" onClick={reset} style={{marginTop: 16}}>
                    关闭并刷新列表
                </Button>
            )}
          </Space>
        </div>
      )}
    </Modal>
  );
};

export default ImportModal;
