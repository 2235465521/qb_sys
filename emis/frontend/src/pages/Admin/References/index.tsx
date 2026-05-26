import React, { useState } from 'react';
import { Card, Typography, Upload, Button, List, Space, Alert, Row, Col, Badge, message } from 'antd';
import { 
  InboxOutlined, 
  InfoCircleOutlined, 
  LineChartOutlined, 
  DeleteOutlined, 
  FileExcelOutlined,
  PlayCircleOutlined,
  WarningOutlined
} from '@ant-design/icons';
import { useAnalysisData } from '@/hooks/useAnalysisData';
import apiClient from '@/api/client';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;

const AdminReferencesPage: React.FC = () => {
  // 规范性引用导入状态与处理
  const [selectedRefFiles, setSelectedRefFiles] = useState<File[]>([]);
  const { uploadMutation } = useAnalysisData();

  const beforeRefUpload = (file: File) => {
    setSelectedRefFiles(prev => {
      if (prev.some(f => f.name === file.name)) {
        return prev;
      }
      return [...prev, file];
    });
    return false;
  };

  const handleRefRemove = (fileName: string) => {
    setSelectedRefFiles(prev => prev.filter(f => f.name !== fileName));
  };

  const handleRefClearAll = () => {
    setSelectedRefFiles([]);
  };

  const handleStartRefUpload = () => {
    if (selectedRefFiles.length === 0) return;
    uploadMutation.mutate(selectedRefFiles, {
      onSuccess: () => {
        setSelectedRefFiles([]);
      }
    });
  };

  // 指标解析导入状态与处理
  const [selectedIndFiles, setSelectedIndFiles] = useState<File[]>([]);
  const [importingIndicators, setImportingIndicators] = useState(false);
  const [indUploadResults, setIndUploadResults] = useState<any[] | null>(null);

  const beforeIndUpload = (file: File) => {
    setSelectedIndFiles(prev => {
      if (prev.some(f => f.name === file.name)) {
        return prev;
      }
      return [...prev, file];
    });
    return false;
  };

  const handleIndRemove = (fileName: string) => {
    setSelectedIndFiles(prev => prev.filter(f => f.name !== fileName));
  };

  const handleIndClearAll = () => {
    setSelectedIndFiles([]);
    setIndUploadResults(null);
  };

  const handleStartIndUpload = async () => {
    if (selectedIndFiles.length === 0) return;
    setImportingIndicators(true);
    setIndUploadResults(null);
    const results = [];
    for (const file of selectedIndFiles) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const { data } = await apiClient.post('/admin/standards/import-indicators/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        results.push({
          fileName: file.name,
          success: true,
          message: data.message || '状态导入更新成功'
        });
      } catch (err: any) {
        results.push({
          fileName: file.name,
          success: false,
          message: err.response?.data?.error || err.message || '上传或请求出错'
        });
      }
    }
    setIndUploadResults(results);
    setImportingIndicators(false);
    setSelectedIndFiles([]);

    const failures = results.filter(r => !r.success);
    if (failures.length > 0) {
      message.warning(`批量导入更新完成，但有 ${failures.length} 个文件处理失败`);
    } else {
      message.success(`成功导入并更新了 ${results.length} 个指标 Excel 文件！`);
    }
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  return (
    <div className="admin-references-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
      <div 
        style={{ 
          marginBottom: 20, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 2px 10px rgba(0,0,0,0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#1677ff', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <LineChartOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#1a1a1a', fontWeight: 'bold' }}>引用及指标解析管理</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#666' }}>
              支持批量导入规范性引用关系 Excel，利用 Celery 解析引用链，并提供独立的指标解析 Excel 状态批量打标导入通道。
            </p>
          </div>
        </div>
      </div>

      <Row gutter={24}>
        {/* 左半侧：规范性引用解析 */}
        <Col xs={24} lg={12}>
          <Card 
            title={<Space><InboxOutlined style={{ color: '#1677ff' }} /><span style={{ color: '#1677ff', fontWeight: 'bold' }}>已完成规范性引用解析</span></Space>}
            bordered={false} 
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.03)', border: '1px solid #f0f0f0', minHeight: '520px' }}
          >
            <Paragraph>
              请拖拽或选择一个或多个 Excel 文件进行引用链深度溯源解析。系统会自动检测文件列格式并对齐企业和标准。
            </Paragraph>
            
            <Alert
              message="规范性引用 Excel 支持格式"
              description="双模兼容：① 两列兼容格式（A列企标号，B列被引标准号）；② 十列批次格式（包含企标号、公司名称、最新标准号等）。"
              type="info"
              showIcon
              style={{ marginBottom: 20 }}
            />

            {/* 拖拽上传区 */}
            <div style={{ marginBottom: 20 }}>
              <Dragger 
                accept=".xlsx,.xls"
                multiple
                beforeUpload={beforeRefUpload}
                showUploadList={false}
                disabled={uploadMutation.isPending}
                style={{
                  background: '#fafafa',
                  border: '2px dashed #d9d9d9',
                  borderRadius: 8,
                  padding: '24px 0',
                  transition: 'border 0.3s'
                }}
              >
                <p className="ant-upload-drag-icon" style={{ marginBottom: 12 }}>
                  <InboxOutlined style={{ fontSize: 48, color: '#1677ff' }} />
                </p>
                <p className="ant-upload-text" style={{ fontSize: 15, fontWeight: 500, color: '#262626' }}>
                  将规范性引用 Excel 文件拖拽到此处，或点击选择
                </p>
                <p className="ant-upload-hint" style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
                  支持多选批量上传，单文件最大 20MB (.xlsx, .xls)
                </p>
              </Dragger>
            </div>

            {/* 待上传队列显示 */}
            {selectedRefFiles.length > 0 && (
              <Card 
                size="small" 
                title={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>待解析引用队列 ({selectedRefFiles.length} 个文件)</span>
                    <Button type="link" size="small" onClick={handleRefClearAll} danger>清空队列</Button>
                  </div>
                }
                style={{ marginBottom: 20, background: '#fcfcfc', borderRadius: 8 }}
              >
                <List
                  size="small"
                  dataSource={selectedRefFiles}
                  renderItem={(file) => (
                    <List.Item 
                      actions={[
                        <Button 
                          type="text" 
                          icon={<DeleteOutlined />} 
                          onClick={() => handleRefRemove(file.name)} 
                          danger 
                        />
                      ]}
                    >
                      <Space>
                        <FileExcelOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                        <Text strong style={{ fontSize: 13 }}>{file.name}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>({formatBytes(file.size)})</Text>
                      </Space>
                    </List.Item>
                  )}
                />
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Button 
                    type="primary" 
                    icon={<PlayCircleOutlined />}
                    onClick={handleStartRefUpload}
                    loading={uploadMutation.isPending}
                    style={{ borderRadius: 6 }}
                  >
                    开始批量解析引用
                  </Button>
                </div>
              </Card>
            )}

            {/* 上传解析报告呈现 */}
            {uploadMutation.data && (
              <div style={{ marginTop: 24 }}>
                <Title level={5} style={{ marginBottom: 12 }}>📋 批量解析引用报告</Title>
                <List
                  dataSource={uploadMutation.data}
                  renderItem={(item: any) => (
                    <Card 
                      size="small"
                      style={{ 
                        marginBottom: 12, 
                        borderRadius: 8, 
                        border: item.success ? '1px solid #d9f7be' : '1px solid #ffccc7',
                        background: item.success ? '#f6ffed' : '#fff2f0'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                        <Space>
                          <FileExcelOutlined style={{ color: item.success ? '#52c41a' : '#ff4d4f', fontSize: 16 }} />
                          <Text strong style={{ fontSize: 14 }}>{item.fileName}</Text>
                        </Space>
                        <Badge 
                          status={item.success ? (item.errors.length > 0 ? 'warning' : 'success') : 'error'} 
                          text={item.success ? (item.errors.length > 0 ? '存在警告' : '解析成功') : '解析失败'} 
                        />
                      </div>
                      
                      {item.success ? (
                        <div style={{ fontSize: 12, color: '#595959', paddingLeft: 22 }}>
                          <Space size="large">
                            <span>已解析企标: <Text strong type="success">{item.parsed_standards}</Text> 个</span>
                            <span>新增/更新引用: <Text strong type="success">{item.citations_added}</Text> 条</span>
                          </Space>
                        </div>
                      ) : null}

                      {item.errors && item.errors.length > 0 && (
                        <div style={{ marginTop: 8, padding: '8px 12px', background: '#fff', borderRadius: 4, borderLeft: '3px solid #ff4d4f' }}>
                          <div style={{ fontWeight: 'bold', fontSize: 12, color: '#ff4d4f', marginBottom: 4 }}>
                            <WarningOutlined /> 异常/错误详情 ({item.errors.length} 条)
                          </div>
                          <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: '#8c8c8c' }}>
                            {item.errors.slice(0, 5).map((err: string, i: number) => (
                              <li key={i}>{err}</li>
                            ))}
                            {item.errors.length > 5 && <li>以及其他 {item.errors.length - 5} 个异常...</li>}
                          </ul>
                        </div>
                      )}
                    </Card>
                  )}
                />
              </div>
            )}
          </Card>
        </Col>

        {/* 右半侧：指标解析 */}
        <Col xs={24} lg={12}>
          <Card 
            title={<Space><InboxOutlined style={{ color: '#52c41a' }} /><span style={{ color: '#52c41a', fontWeight: 'bold' }}>完成指标解析</span></Space>}
            bordered={false} 
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.03)', border: '1px solid #f0f0f0', minHeight: '520px' }}
          >
            <Paragraph>
              请拖拽或选择一个或多个 Excel 文件进行指标数据批量导入。系统会自动识别企标并将解析状态强制标记为“已完成指标解析”。
            </Paragraph>
            
            <Alert
              message="指标解析 Excel 支持格式"
              description="单列或多列格式：Excel 中必须包含名为“标准编号”、“企标号”或“标准号”的列，导入后对应企标状态将强制更新为“已完成指标解析”。"
              type="warning"
              showIcon
              style={{ marginBottom: 20 }}
            />

            {/* 拖拽上传区 */}
            <div style={{ marginBottom: 20 }}>
              <Dragger 
                accept=".xlsx,.xls"
                multiple
                beforeUpload={beforeIndUpload}
                showUploadList={false}
                disabled={importingIndicators}
                style={{
                  background: '#fafafa',
                  border: '2px dashed #d9d9d9',
                  borderRadius: 8,
                  padding: '24px 0',
                  transition: 'border 0.3s'
                }}
              >
                <p className="ant-upload-drag-icon" style={{ marginBottom: 12 }}>
                  <InboxOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                </p>
                <p className="ant-upload-text" style={{ fontSize: 15, fontWeight: 500, color: '#262626' }}>
                  将指标解析 Excel 文件拖拽到此处，或点击选择
                </p>
                <p className="ant-upload-hint" style={{ fontSize: 12, color: '#8c8c8c', marginTop: 4 }}>
                  支持多选批量上传，单文件最大 20MB (.xlsx, .xls)
                </p>
              </Dragger>
            </div>

            {/* 待上传队列显示 */}
            {selectedIndFiles.length > 0 && (
              <Card 
                size="small" 
                title={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>待解析指标队列 ({selectedIndFiles.length} 个文件)</span>
                    <Button type="link" size="small" onClick={handleIndClearAll} danger>清空队列</Button>
                  </div>
                }
                style={{ marginBottom: 20, background: '#fcfcfc', borderRadius: 8 }}
              >
                <List
                  size="small"
                  dataSource={selectedIndFiles}
                  renderItem={(file) => (
                    <List.Item 
                      actions={[
                        <Button 
                          type="text" 
                          icon={<DeleteOutlined />} 
                          onClick={() => handleIndRemove(file.name)} 
                          danger 
                        />
                      ]}
                    >
                      <Space>
                        <FileExcelOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                        <Text strong style={{ fontSize: 13 }}>{file.name}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>({formatBytes(file.size)})</Text>
                      </Space>
                    </List.Item>
                  )}
                />
                <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Button 
                    type="primary" 
                    icon={<PlayCircleOutlined />}
                    onClick={handleStartIndUpload}
                    loading={importingIndicators}
                    style={{ borderRadius: 6, background: '#52c41a', borderColor: '#52c41a' }}
                  >
                    开始批量更新状态
                  </Button>
                </div>
              </Card>
            )}

            {/* 上传解析报告呈现 */}
            {indUploadResults && (
              <div style={{ marginTop: 24 }}>
                <Title level={5} style={{ marginBottom: 12 }}>📋 批量导入指标报告</Title>
                <List
                  dataSource={indUploadResults}
                  renderItem={(item: any) => (
                    <Card 
                      size="small"
                      style={{ 
                        marginBottom: 12, 
                        borderRadius: 8, 
                        border: item.success ? '1px solid #d9f7be' : '1px solid #ffccc7',
                        background: item.success ? '#f6ffed' : '#fff2f0'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Space>
                          <FileExcelOutlined style={{ color: item.success ? '#52c41a' : '#ff4d4f', fontSize: 16 }} />
                          <Text strong style={{ fontSize: 14 }}>{item.fileName}</Text>
                        </Space>
                        <Badge 
                          status={item.success ? 'success' : 'error'} 
                          text={item.success ? '导入更新成功' : '导入更新失败'} 
                        />
                      </div>
                      <div style={{ fontSize: 12, color: '#595959', paddingLeft: 22, marginTop: 8 }}>
                        {item.message}
                      </div>
                    </Card>
                  )}
                />
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* 说明放在最下端，满宽展示，方便查阅 */}
      <Row gutter={24} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card 
            title={<Space><InfoCircleOutlined style={{ color: '#fa8c16' }} /> 解析处理规则说明</Space>}
            bordered={false}
            style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.03)', border: '1px solid #f0f0f0' }}
          >
            <Paragraph strong>1. 企标解析打标原则</Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 13 }}>
              系统对符合条件的企标进行 <Text code>is_parsed</Text> 标记。如果 Excel 中包含系统中<Text strong>企业库尚未关联入库的企标</Text>，系统在 10 列批次模式下会自动为您在后台建档企业并入库标准。
            </Paragraph>

            <Paragraph strong style={{ marginTop: 16 }}>2. 最新标准号强制覆盖</Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 13 }}>
              如果数据库中已存在某条引用链（例如从历史两列模式导入的记录），只要本次上传的 Excel 中提供了非空的 <Text strong>“最新标准号”</Text>，系统将智能识别差量并<Text strong>强制执行覆盖更新</Text>，实时纠正历史引用对齐偏差。
            </Paragraph>

            <Paragraph strong style={{ marginTop: 16 }}>3. 引用热度实时累加</Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 13 }}>
              系统底层会自动为引用的国家标准进行被引热度（<Text code>citation_count</Text>）统计。新增的引用链条在 Celery 解析完成后，将即时累加并在首页大屏的引用排行榜中直观展示。
            </Paragraph>

            <Paragraph strong style={{ marginTop: 16 }}>4. 批量处理与性能</Paragraph>
            <Paragraph type="secondary" style={{ fontSize: 13 }}>
              由于后台基于 Celery 异步通信通道，您的所有批量文件都将依次送入独立子线程并发流式解析。即使单次上传数万条引用数据，也无需担心前端网页卡死，您可以随时刷新或在引用看板中观察解析成果。
            </Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default AdminReferencesPage;

