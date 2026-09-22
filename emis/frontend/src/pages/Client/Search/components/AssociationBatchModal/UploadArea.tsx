import React, { useState } from 'react';
import { Upload, Tabs, Input, Button, Typography, Alert } from 'antd';
import { InboxOutlined, FileExcelOutlined, EditOutlined, ThunderboltOutlined } from '@ant-design/icons';

const { Dragger } = Upload;
const { Paragraph } = Typography;
const { TextArea } = Input;

interface UploadAreaProps {
  loading: boolean;
  onFileSelect: (file: File) => void;
  onTextSubmit: (names: string[]) => void;
}

export const UploadArea: React.FC<UploadAreaProps> = ({ loading, onFileSelect, onTextSubmit }) => {
  const [activeTab, setActiveTab] = useState<'excel' | 'text'>('excel');
  const [textInput, setTextInput] = useState<string>('');

  const handleTextAnalyze = () => {
    const lines = textInput
      .split('\n')
      .map((l) => l.trim())
      .filter((l) => l.length > 1);
    onTextSubmit(lines);
  };

  return (
    <div style={{ padding: '8px 0' }}>
      <Alert
        message="智能批量查标服务说明"
        description="系统将自动从 Excel 中提取社团组织名称，并发穿透国家标准库、团体标准库与本地企标库，汇总每家协会起草与归口的标准资产，支持一键合并导出至一张汇总 Excel 报表。"
        type="info"
        showIcon
        style={{ marginBottom: 20, borderRadius: 8 }}
      />

      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as any)}
        centered
        items={[
          {
            key: 'excel',
            label: (
              <span>
                <FileExcelOutlined style={{ marginRight: 6, color: '#0d9488' }} />
                上传 Excel 名单文件
              </span>
            ),
            children: (
              <div style={{ margin: '16px 0' }}>
                <Dragger
                  accept=".xlsx,.xls,.csv"
                  showUploadList={false}
                  beforeUpload={(file) => {
                    onFileSelect(file);
                    return false;
                  }}
                  disabled={loading}
                  style={{
                    padding: '36px 20px',
                    borderRadius: 12,
                    background: '#f8fafc',
                    border: '2px dashed #0d9488',
                  }}
                >
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined style={{ color: '#0d9488', fontSize: 48 }} />
                  </p>
                  <p style={{ fontSize: 16, fontWeight: 600, color: '#1e293b', marginBottom: 8 }}>
                    点击或将社团名单 Excel 拖拽至此处
                  </p>
                  <Paragraph type="secondary" style={{ fontSize: 13, marginBottom: 0 }}>
                    支持 .xlsx / .xls 格式。系统会自动定位“社团名称/协会名称/单位名称”列，首列为序号的表格可无缝兼容。
                  </Paragraph>
                </Dragger>
              </div>
            ),
          },
          {
            key: 'text',
            label: (
              <span>
                <EditOutlined style={{ marginRight: 6, color: '#0d9488' }} />
                粘贴社团名称文本
              </span>
            ),
            children: (
              <div style={{ margin: '16px 0' }}>
                <TextArea
                  rows={8}
                  placeholder={`福建省联合采购协会\n泉州市会展业联合会\n福建省地震学会\n福建省智能制造发展促进会\n福州市软件行业协会\n（每行一个社团/协会名称）`}
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  style={{ borderRadius: 8, fontSize: 13, fontFamily: 'monospace' }}
                  disabled={loading}
                />
                <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button
                    type="primary"
                    icon={<ThunderboltOutlined />}
                    loading={loading}
                    disabled={!textInput.trim()}
                    onClick={handleTextAnalyze}
                    style={{
                      borderRadius: 20,
                      background: 'linear-gradient(135deg, #13c2c2 0%, #0d9488 100%)',
                      borderColor: '#0d9488',
                      padding: '0 24px',
                    }}
                  >
                    开始解析与查标
                  </Button>
                </div>
              </div>
            ),
          },
        ]}
      />
    </div>
  );
};
