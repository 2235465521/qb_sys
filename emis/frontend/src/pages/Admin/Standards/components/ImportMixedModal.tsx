import React, { useState, useEffect, useRef } from 'react';
import { Modal, Upload, message, Typography, Button, Table, Alert, Progress, Space, Statistic, Row, Col, Card } from 'antd';
import { InboxOutlined, DownloadOutlined, LoadingOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Dragger } = Upload;
const { Text } = Typography;

interface ImportMixedModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

interface ValidationError {
  row: number;
  reason: string;
}

interface ImportTaskResult {
  status: 'pending' | 'running' | 'done' | 'failed';
  progress?: number;
  success_count?: number;
  failed_count?: number;
  errors?: ValidationError[];
  error?: string;
}

const ImportMixedModal: React.FC<ImportMixedModalProps> = ({ open, onCancel, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<ImportTaskResult | null>(null);
  
  const pollTimerRef = useRef<any>(null);

  // 下载混合导入模板
  const handleDownloadTemplate = async () => {
    try {
      const response = await apiClient.get('/admin/standards/import-mixed/template/', {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', '企业标准与引用关系混合导入模板.xlsx');
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

  // 上传混合 Excel 启动 Celery 任务
  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setTaskId(null);
    setTaskStatus(null);
    
    try {
      const { data } = await apiClient.post<{ task_id: string; message: string }>('/admin/standards/import-mixed/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTaskId(data.task_id);
      setTaskStatus({ status: 'pending', progress: 0 });
      message.success('文件上传成功，已提交后台排队处理');
    } catch (error: any) {
      const errMsg = error?.response?.data?.error || '上传解析失败，请检查文件模版';
      message.error(errMsg);
      setUploading(false);
    }
    return false; // 阻止默认自动上传
  };

  // 轮询任务状态
  useEffect(() => {
    if (!taskId) return;

    const pollStatus = async () => {
      try {
        const { data } = await apiClient.get<ImportTaskResult>('/admin/standards/import-mixed/status/', {
          params: { task_id: taskId }
        });
        
        setTaskStatus(data);

        if (data.status === 'done') {
          stopPolling();
          setUploading(false);
          message.success(`异步导入完成！成功入库 ${data.success_count} 条记录。`);
          onSuccess();
        } else if (data.status === 'failed') {
          stopPolling();
          setUploading(false);
          message.error(`导入任务失败: ${data.error || '未知错误'}`);
        }
      } catch (err) {
        // 轮询网络抖动时不中断
        console.error('轮询状态出错:', err);
      }
    };

    pollTimerRef.current = setInterval(pollStatus, 1500);

    return () => stopPolling();
  }, [taskId]);

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const reset = () => {
    stopPolling();
    setTaskId(null);
    setTaskStatus(null);
    setUploading(false);
    onCancel();
  };

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
      title: '错误原因说明',
      dataIndex: 'reason',
      key: 'reason',
      render: (text: string) => (
        <Text type="danger" style={{ fontSize: 13, fontWeight: 500 }}>
          {text}
        </Text>
      )
    }
  ];

  const getProgressStatus = () => {
    if (!taskStatus) return 'normal';
    if (taskStatus.status === 'failed') return 'exception';
    if (taskStatus.status === 'done') return 'success';
    return 'active';
  };

  return (
    <Modal
      title={<span style={{ fontSize: 18, fontWeight: 'bold' }}>异步解耦批量导入企标与引用</span>}
      open={open}
      onCancel={reset}
      footer={null}
      width={700}
      destroyOnClose
      maskClosable={!uploading}
      closable={!uploading}
    >
      {!taskId ? (
        <>
          <div style={{ marginBottom: 20 }}>
            <Text type="secondary" style={{ display: 'block', lineHeight: '1.6', marginBottom: 12 }}>
              支持上传混合表模板，同时批量建立企业标准基本信息以及规范性引用映射关系。
              采用 **Celery 异步解耦任务** 与 **行级数据库事务**，避免服务器超时卡死。
            </Text>
            
            <Button
              type="primary"
              ghost
              icon={<DownloadOutlined />}
              onClick={handleDownloadTemplate}
              style={{ borderRadius: 6 }}
            >
              下载混合表导入模板 (.xlsx)
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
              <InboxOutlined style={{ color: '#1677ff' }} />
            </p>
            <p className="ant-upload-text" style={{ fontWeight: 500 }}>点击或将填写完成的混合表拖拽到此区域上传</p>
            <p className="ant-upload-hint" style={{ fontSize: 12 }}>
              支持 .xlsx 或 .xls 格式，必须包含企业信息、企标编号、引用的标准编号核心字段。
            </p>
          </Dragger>
        </>
      ) : (
        <div style={{ padding: '8px 0' }}>
          <Alert
            message={
              <Space>
                {taskStatus?.status === 'running' || taskStatus?.status === 'pending' ? (
                  <LoadingOutlined spin style={{ color: '#1677ff' }} />
                ) : null}
                <span style={{ fontWeight: 'bold' }}>
                  {taskStatus?.status === 'pending' && '等待任务启动排队中...'}
                  {taskStatus?.status === 'running' && '后台异步拆分与事务入库执行中...'}
                  {taskStatus?.status === 'done' && '异步导入任务完成'}
                  {taskStatus?.status === 'failed' && '任务执行失败'}
                </span>
              </Space>
            }
            description={
              taskStatus?.status === 'running'
                ? `系统正在解析并导入数据行，当前进度 ${taskStatus.progress || 0}%。此时可安全关闭此弹窗，后台仍将继续导入。`
                : taskStatus?.status === 'done'
                ? `本次任务已圆满结束，成功导入主子表条数见下方报告。`
                : `任务执行遇到了致命异常导致中断，请检查 Excel 的核心列头和结构。`
            }
            type={
              taskStatus?.status === 'done'
                ? 'success'
                : taskStatus?.status === 'failed'
                ? 'error'
                : 'info'
            }
            showIcon={taskStatus?.status === 'done' || taskStatus?.status === 'failed'}
            style={{ marginBottom: 24, borderRadius: 8 }}
          />

          <div style={{ marginBottom: 24 }}>
            <Progress
              percent={taskStatus?.progress ?? (taskStatus?.status === 'done' ? 100 : 0)}
              status={getProgressStatus() as any}
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#87d068',
              }}
            />
          </div>

          {taskStatus?.status === 'done' && (
            <Row gutter={16} style={{ marginBottom: 20 }}>
              <Col span={12}>
                <Card size="small" bordered style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                  <Statistic
                    title="成功事务入库"
                    value={taskStatus.success_count || 0}
                    valueStyle={{ color: '#389e0d', fontWeight: 'bold' }}
                    suffix="条"
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" bordered style={{ background: '#fff1f0', border: '1px solid #ffa39e' }}>
                  <Statistic
                    title="校验失败行数"
                    value={taskStatus.failed_count || 0}
                    valueStyle={{ color: '#cf1322', fontWeight: 'bold' }}
                    suffix="条"
                  />
                </Card>
              </Col>
            </Row>
          )}

          {taskStatus?.errors && taskStatus.errors.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8, color: '#cf1322' }}>
                行级数据校验报错日志清单：
              </Text>
              <Table
                columns={columns}
                dataSource={taskStatus.errors.map((err, idx) => ({ ...err, key: idx }))}
                size="small"
                bordered
                pagination={{ pageSize: 5, showSizeChanger: false }}
                style={{ borderRadius: 8, overflow: 'hidden' }}
              />
            </div>
          )}

          {taskStatus?.status === 'done' && (
            <div style={{ textAlign: 'right', marginTop: 24 }}>
              <Button type="primary" onClick={reset} style={{ borderRadius: 6 }}>
                确 定
              </Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};

export default ImportMixedModal;
