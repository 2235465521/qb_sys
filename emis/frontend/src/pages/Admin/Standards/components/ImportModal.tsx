import React, { useState } from 'react';
import { Modal, Upload, message, Typography, List, Card, Col, Row, Statistic } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
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
      const { data } = await apiClient.post('/admin/standards/import/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(data);
      if (data.success > 0 || data.companies_created > 0 || data.companies_updated > 0) {
        message.success(`导入完成！新增企标资产 ${data.success} 条`);
        onSuccess();
      } else if (data.errors.length === 0) {
        message.warning('Excel 中所有记录均已存在，已自动过滤');
      }
    } catch (error) {
      message.error('导入解析失败，请确保上传了正确的爬取 Excel 记录文件');
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
      title={<span style={{ fontSize: 18, fontWeight: 'bold' }}>批量导入企业标准 (按爬虫 Excel 表头)</span>}
      open={open}
      onCancel={reset}
      footer={null}
      width={600}
      destroyOnClose
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary" style={{ display: 'block', lineHeight: '1.6' }}>
          支持拖拽上传您爬取的 <Text strong>《企业标准下载记录.xlsx》</Text> 原格式文件。
          后台将自动执行：
        </Text>
        <ol style={{ paddingLeft: 20, margin: '8px 0', color: '#666', fontSize: 13, lineHeight: '1.8' }}>
          <li>
            自动以“统一社会信用代码”查重并建档/更新企业；
          </li>
          <li>
            对齐 <Text strong>“北京市-海淀区”</Text> 等直辖市或常规省市县，自动级联获取 LBS 国标经纬度进行零成本地图落位；
          </li>
          <li>
            以标准编号生成 `clean_id` 执行去重，自动灌入企标详情并绑定至对应企业下。
          </li>
        </ol>
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
        <p className="ant-upload-text" style={{ fontWeight: 500 }}>点击或将爬取的 Excel 文件拖拽到此区域上传</p>
        <p className="ant-upload-hint" style={{ fontSize: 12 }}>
          {uploading ? '系统正在高速读取双表联合写入中，请稍候...' : '支持 .xlsx 或 .xls 格式，严禁上传非业务无关数据'}
        </p>
      </Dragger>

      {result && (
        <div style={{ marginTop: 24 }}>
          <Text strong style={{ fontSize: 15, display: 'block', marginBottom: 12 }}>
            🎉 企标空间关联导入结果：
          </Text>
          
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card size="small" bordered style={{ background: '#f6ffed', border: '1px solid #b7eb8f' }}>
                <Statistic
                  title="成功导入企标"
                  value={result.success}
                  valueStyle={{ color: '#389e0d' }}
                  suffix="条"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" bordered style={{ background: '#fffbe6', border: '1px solid #ffe58f' }}>
                <Statistic
                  title="过滤重复企标"
                  value={result.skipped}
                  valueStyle={{ color: '#d46b08' }}
                  suffix="条"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" bordered style={{ background: '#e6f7ff', border: '1px solid #91d5ff' }}>
                <Statistic
                  title="建档新企业"
                  value={result.companies_created}
                  valueStyle={{ color: '#096dd9' }}
                  suffix="家"
                />
              </Card>
            </Col>
            <Col span={12}>
              <Card size="small" bordered style={{ background: '#f9f0ff', border: '1px solid #d3adf7' }}>
                <Statistic
                  title="补充更新旧企业"
                  value={result.companies_updated}
                  valueStyle={{ color: '#531dab' }}
                  suffix="家"
                />
              </Card>
            </Col>
          </Row>

          {result.errors && result.errors.length > 0 && (
            <div>
              <Text type="danger" strong style={{ display: 'block', marginBottom: 8 }}>
                异常行记录详情：
              </Text>
              <List
                size="small"
                bordered
                dataSource={result.errors}
                renderItem={(item: string) => (
                  <List.Item>
                    <Text type="danger" style={{ fontSize: 12 }}>
                      {item}
                    </Text>
                  </List.Item>
                )}
                style={{ maxHeight: 150, overflow: 'auto', borderRadius: 8 }}
              />
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};

export default ImportModal;
