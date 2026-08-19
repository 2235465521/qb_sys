import React, { useState, useEffect, useRef } from 'react';
import { Modal, Upload, message, Typography, Button, Table, Alert, Progress, Space, Statistic, Row, Col, Card, List } from 'antd';
import { InboxOutlined, DownloadOutlined, LoadingOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Dragger } = Upload;
const { Text } = Typography;

interface SmartImportModalProps {
  open: boolean;
  onCancel: () => void;
  onSuccess: () => void;
}

interface ValidationError {
  row: number;
  error?: string;
  reason?: string;
}

interface ImportTaskResult {
  status: 'pending' | 'running' | 'done' | 'failed';
  progress?: number;
  success_count?: number;
  failed_count?: number;
  errors?: ValidationError[];
  error?: string;
}

const SmartImportModal: React.FC<SmartImportModalProps> = ({ open, onCancel, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  
  // 异步任务状态
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<ImportTaskResult | null>(null);
  
  // 同步任务状态
  const [syncResult, setSyncResult] = useState<any>(null);

  const pollTimerRef = useRef<any>(null);

  const handleDownloadTemplate = async (type: string, filename: string) => {
    try {
      let url = '';
      if (type === 'mixed') url = '/admin/standards/import-mixed/template/';
      else if (type === 'reference') url = '/admin/standards/import-references/template/';
      else url = '/admin/standards/import/template/';

      const response = await apiClient.get(url, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(objectUrl);
      message.success(`下载模板 ${filename} 成功！`);
    } catch (err) {
      console.error(err);
      message.error('下载模板失败，请稍后重试');
    }
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);

    setUploading(true);
    setTaskId(null);
    setTaskStatus(null);
    setSyncResult(null);
    
    try {
      const { data } = await apiClient.post('/admin/standards/import-smart/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000, // 5分钟，应对同步导入超大文件与扫描PDF挂载盘
      });

      if (data.type === 'async') {
        setTaskId(data.task_id);
        setTaskStatus({ status: 'pending', progress: 0 });
        message.success(data.message || '文件已提交后台排队处理');
      } else if (data.type === 'sync') {
        setUploading(false);
        setSyncResult(data.data);
        const successCount = (data.data?.success || 0) + (data.data?.success_count || 0);
        const skippedCount = data.data?.skipped || 0;
        if (successCount === 0 && skippedCount === 0 && (!data.data?.errors || data.data.errors.length === 0)) {
          message.warning(data.message || '导入解析完成，但未发现有效数据行');
        } else {
          message.success(data.message || `同步导入解析完成（成功 ${successCount} 条，跳过重复 ${skippedCount} 条）`);
        }
        onSuccess();
      }
    } catch (error: any) {
      const respData = error?.response?.data;
      const errMsg = respData?.error || respData?.detail || respData?.message || error?.message || '上传解析失败，请检查文件模版';
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
          message.success(`异步导入完成！成功入库 ${data.success_count || 0} 条记录。`);
          onSuccess();
        } else if (data.status === 'failed') {
          stopPolling();
          setUploading(false);
          message.error(`导入任务失败: ${data.error || '未知错误'}`);
        }
      } catch (err) {
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
    setSyncResult(null);
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
      dataIndex: 'error',
      key: 'error',
      render: (text: string, record: any) => (
        <Text type="danger" style={{ fontSize: 13, fontWeight: 500 }}>
          {text || record.reason || '未知错误'}
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
      title={<span style={{ fontSize: 18, fontWeight: 'bold' }}>智能导入数据 (自动识别表头)</span>}
      open={open}
      onCancel={reset}
      footer={null}
      width={700}
      destroyOnClose
      maskClosable={!uploading}
      closable={!uploading}
    >
      {!taskId && !syncResult ? (
        <>
          <div style={{ marginBottom: 20 }}>
            <Text type="secondary" style={{ display: 'block', lineHeight: '1.6', marginBottom: 12 }}>
              上传任意包含 **核心字段** 的 Excel 文件，系统将**自动识别**表头并智能分发至对应的入库逻辑（纯企标、纯引用、或混合入库）。
            </Text>
            
            <Space wrap>
              <Button size="small" onClick={() => handleDownloadTemplate('company', '企业标准导入模板.xlsx')}>
                下载企标模板
              </Button>
              <Button size="small" onClick={() => handleDownloadTemplate('reference', '引用关系导入模板.xlsx')}>
                下载引用模板
              </Button>
              <Button size="small" type="primary" ghost icon={<DownloadOutlined />} onClick={() => handleDownloadTemplate('mixed', '混合智能导入模板.xlsx')}>
                下载混合表模板 (推荐)
              </Button>
            </Space>
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
            <p className="ant-upload-text" style={{ fontWeight: 500 }}>点击或将 Excel 文件拖拽到此区域智能上传</p>
            <p className="ant-upload-hint" style={{ fontSize: 12 }}>
              系统会根据“引用的标准号”、“统一社会信用代码”等特征自动判别导入类型
            </p>
          </Dragger>
        </>
      ) : taskId ? (
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
                  {taskStatus?.status === 'done' && '异步混合导入任务完成'}
                  {taskStatus?.status === 'failed' && '任务执行失败'}
                </span>
              </Space>
            }
            description={
              taskStatus?.status === 'running'
                ? `系统正在解析并混合导入数据行，当前进度 ${taskStatus.progress || 0}%。`
                : taskStatus?.status === 'done'
                ? `本次任务已圆满结束，成功导入主子表条数见下方报告。`
                : `任务执行遇到了异常，请检查 Excel 结构。`
            }
            type={taskStatus?.status === 'done' ? 'success' : taskStatus?.status === 'failed' ? 'error' : 'info'}
            showIcon={taskStatus?.status === 'done' || taskStatus?.status === 'failed'}
            style={{ marginBottom: 24, borderRadius: 8 }}
          />

          <div style={{ marginBottom: 24 }}>
            <Progress
              percent={taskStatus?.progress ?? (taskStatus?.status === 'done' ? 100 : 0)}
              status={getProgressStatus() as any}
            />
          </div>

          {taskStatus?.status === 'done' && (
            <Row gutter={16} style={{ marginBottom: 20 }}>
              <Col span={12}>
                <Card size="small" bordered style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                  <Statistic title="成功入库" value={taskStatus.success_count || 0} valueStyle={{ color: '#389e0d', fontWeight: 'bold' }} suffix="条" />
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" bordered style={{ background: '#fff1f0', border: '1px solid #ffa39e' }}>
                  <Statistic title="校验失败" value={taskStatus.failed_count || 0} valueStyle={{ color: '#cf1322', fontWeight: 'bold' }} suffix="条" />
                </Card>
              </Col>
            </Row>
          )}

          {taskStatus?.errors && taskStatus.errors.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8, color: '#cf1322' }}>错误日志：</Text>
              <Table
                columns={columns}
                dataSource={taskStatus.errors.map((err, idx) => ({ ...err, key: idx }))}
                size="small"
                bordered
                pagination={{ pageSize: 5 }}
              />
            </div>
          )}

          {taskStatus?.status === 'done' && (
            <div style={{ textAlign: 'right', marginTop: 24 }}>
              <Button type="primary" onClick={reset} style={{ borderRadius: 6 }}>确 定</Button>
            </div>
          )}
        </div>
      ) : (
        <div style={{ padding: '8px 0' }}>
          <Alert
            message={<span style={{ fontWeight: 'bold' }}>同步解析导入完成</span>}
            description={`系统判定该文件属于单一导入类型（纯企标或纯引用），已同步完成入库。`}
            type="success"
            showIcon
            style={{ marginBottom: 24, borderRadius: 8 }}
          />
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {syncResult.success !== undefined && (
              <Col span={8}>
                <Card size="small" bordered style={{ background: '#f6ffed' }}>
                  <Statistic title="成功企标/引用" value={syncResult.success || syncResult.success_count || 0} valueStyle={{ color: '#389e0d' }} suffix="条" />
                </Card>
              </Col>
            )}
            {syncResult.companies_created !== undefined && (
              <Col span={8}>
                <Card size="small" bordered style={{ background: '#e6f4ff' }}>
                  <Statistic title="新注册企业" value={syncResult.companies_created || 0} valueStyle={{ color: '#1677ff' }} />
                </Card>
              </Col>
            )}
            {syncResult.companies_updated !== undefined && (
              <Col span={8}>
                <Card size="small" bordered style={{ background: '#e6f4ff' }}>
                  <Statistic title="更新企业" value={syncResult.companies_updated || 0} valueStyle={{ color: '#1677ff' }} />
                </Card>
              </Col>
            )}
            {syncResult.skipped !== undefined && (
              <Col span={8}>
                <Card size="small" bordered style={{ background: '#fffbe6' }}>
                  <Statistic title="跳过重复项" value={syncResult.skipped || 0} valueStyle={{ color: '#faad14' }} />
                </Card>
              </Col>
            )}
          </Row>

          {syncResult.errors && syncResult.errors.length > 0 && (
            <div>
              <Text strong style={{ fontSize: 14, display: 'block', marginBottom: 8, color: '#cf1322' }}>警告 / 错误：</Text>
              <List
                size="small"
                bordered
                dataSource={syncResult.errors}
                renderItem={(item: any) => (
                  <List.Item style={{ color: '#cf1322', fontSize: 13 }}>
                    {typeof item === 'string' ? item : `第 ${item.row} 行: ${item.error || item.reason}`}
                  </List.Item>
                )}
                style={{ maxHeight: 200, overflowY: 'auto' }}
              />
            </div>
          )}

          <div style={{ textAlign: 'right', marginTop: 24 }}>
            <Button type="primary" onClick={reset} style={{ borderRadius: 6 }}>确 定</Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default SmartImportModal;
