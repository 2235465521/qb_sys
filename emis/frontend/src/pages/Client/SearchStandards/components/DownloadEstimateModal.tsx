import React, { useState, useEffect } from 'react';
import { Modal, Radio, Button, Spin, Alert, Typography, Divider, Space, Empty } from 'antd';
import { CloudDownloadOutlined, InfoCircleOutlined, WarningOutlined, FileExcelOutlined, FileZipOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Text, Paragraph } = Typography;

interface DownloadEstimateModalProps {
  open: boolean;
  onCancel: () => void;
  onDownload: (mode: 'zip' | 'excel') => void;
  searchParams: any;
}

interface EstimateData {
  company_count: number;
  files_count: number;
  estimated_size_mb: number;
}

const DownloadEstimateModal: React.FC<DownloadEstimateModalProps> = ({
  open,
  onCancel,
  onDownload,
  searchParams,
}) => {
  const [loading, setLoading] = useState(false);
  const [estimate, setEstimate] = useState<EstimateData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadType, setDownloadType] = useState<'zip' | 'excel'>('zip');

  // 当弹窗打开时，触发预估容量请求
  useEffect(() => {
    if (open) {
      const fetchEstimate = async () => {
        setLoading(true);
        setError(null);
        try {
          const { data } = await apiClient.get<EstimateData>('/client/standards/download-estimate/', {
            params: searchParams
          });
          setEstimate(data);
          // 如果超出阈值，默认选中并只能选择 excel 导出
          if (data.files_count > 500 || data.estimated_size_mb > 500) {
            setDownloadType('excel');
          } else {
            setDownloadType('zip');
          }
        } catch (err: any) {
          console.error(err);
          setError('容量预估计算失败，无法获取服务器估算数据');
        } finally {
          setLoading(false);
        }
      };
      fetchEstimate();
    }
  }, [open, searchParams]);

  const handleConfirm = () => {
    onDownload(downloadType);
  };

  const isOverLimit = estimate ? (estimate.files_count > 500 || estimate.estimated_size_mb > 500) : false;

  return (
    <Modal
      title={
        <Space style={{ color: '#006064', fontWeight: 'bold' }}>
          <CloudDownloadOutlined />
          <span>批量下载与目录导出控制台</span>
        </Space>
      }
      open={open}
      onCancel={onCancel}
      footer={[
        <Button key="back" onClick={onCancel} style={{ borderRadius: 6 }}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          onClick={handleConfirm}
          loading={loading}
          disabled={!estimate}
          style={{
            borderRadius: 6,
            background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
            borderColor: '#00acc1',
          }}
        >
          {downloadType === 'zip' ? '提交打包任务' : '导出目录 Excel'}
        </Button>
      ]}
      width={500}
      centered
      destroyOnClose
    >
      <div style={{ padding: '8px 0' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 12, color: '#666' }}>正在向服务器查询过滤标准的容量预估...</div>
          </div>
        ) : error ? (
          <Alert
            message="错误提示"
            description={error}
            type="error"
            showIcon
          />
        ) : estimate ? (
          <div>
            {/* 警告/提示面板 */}
            {isOverLimit ? (
              <Alert
                message="容量拦截警告"
                description={
                  <div>
                    <Paragraph style={{ margin: 0 }}>
                      当前检索条件包含：<Text strong>{estimate.company_count}</Text> 家企业，
                      共有 <Text strong>{estimate.files_count}</Text> 份关联标准，
                      预估总体积达 <Text strong type="danger">{estimate.estimated_size_mb} MB</Text>。
                    </Paragraph>
                    <Paragraph style={{ margin: '6px 0 0 0', fontWeight: 'bold', color: '#cf1322' }}>
                      <WarningOutlined /> 当前数据量已超出系统单次打包上线限制（500 份 / 500MB）。为了维护服务器稳定性，已拦截全量打包下载。
                    </Paragraph>
                  </div>
                }
                type="error"
                showIcon
                style={{ borderRadius: 8, marginBottom: 16 }}
              />
            ) : (
              <Alert
                message="容量预估就绪"
                description={
                  <div>
                    当前检索条件包含：<Text strong>{estimate.company_count}</Text> 家企业，
                    共有 <Text strong>{estimate.files_count}</Text> 份关联标准，
                    预计打包体积约 <Text strong style={{ color: '#00838f' }}>{estimate.estimated_size_mb} MB</Text>。
                  </div>
                }
                type="info"
                showIcon
                icon={<InfoCircleOutlined style={{ color: '#00838f' }} />}
                style={{ borderRadius: 8, marginBottom: 16, background: '#e0f7fa', borderColor: '#b2ebf2' }}
              />
            )}

            <Divider style={{ margin: '16px 0' }} />

            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 'bold', color: '#595959', marginBottom: 8 }}>选择导出/下载策略：</div>
              <Radio.Group
                value={downloadType}
                onChange={(e) => setDownloadType(e.target.value)}
                style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 10 }}
              >
                <Radio
                  value="zip"
                  disabled={isOverLimit}
                  style={{
                    padding: '10px 14px',
                    border: '1px solid #f0f0f0',
                    borderRadius: 8,
                    background: '#fafafa',
                    width: '100%'
                  }}
                >
                  <Space>
                    <FileZipOutlined style={{ color: isOverLimit ? '#bfbfbf' : '#fa8c16', fontSize: 16 }} />
                    <div>
                      <div style={{ fontWeight: 'bold', color: isOverLimit ? '#bfbfbf' : '#262626' }}>全量打包下载 (ZIP)</div>
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>后台异步打包所有 PDF 文件并提供 Zip 链接</div>
                    </div>
                  </Space>
                </Radio>
                <Radio
                  value="excel"
                  style={{
                    padding: '10px 14px',
                    border: '1px solid #f0f0f0',
                    borderRadius: 8,
                    background: '#fafafa',
                    width: '100%'
                  }}
                >
                  <Space>
                    <FileExcelOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                    <div>
                      <div style={{ fontWeight: 'bold', color: '#262626' }}>导出标准目录清单 (Excel)</div>
                      <div style={{ fontSize: 12, color: '#8c8c8c' }}>下载含标准名、起草单位、被引国标编号的 Excel 信息表</div>
                    </div>
                  </Space>
                </Radio>
              </Radio.Group>
            </div>
          </div>
        ) : (
          <Empty description="暂无容量信息" />
        )}
      </div>
    </Modal>
  );
};

export default DownloadEstimateModal;
