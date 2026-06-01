import React from 'react';
import { Form, Input, Button, Card, Row, Col, Segmented } from 'antd';
import { SearchOutlined, FontSizeOutlined, FileTextOutlined } from '@ant-design/icons';

interface SearchFormProps {
  onSearch: (keyword: string, searchMode: 'title' | 'full_text') => void;
  loading: boolean;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, loading }) => {
  const [form] = Form.useForm();

  const handleFinish = (values: any) => {
    onSearch(values.keyword || '', values.search_mode || 'title');
  };

  return (
    <Card
      bordered={false}
      style={{
        background: 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(8px)',
        borderRadius: 12,
        marginBottom: 16,
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)',
        border: '1px solid rgba(230, 230, 230, 0.6)'
      }}
      bodyStyle={{ padding: '16px 24px' }}
    >
      <Form
        form={form}
        layout="horizontal"
        onFinish={handleFinish}
        initialValues={{ search_mode: 'title' }}
      >
        <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 14, fontWeight: 'bold', color: '#006064' }}>检索模式：</span>
          <Form.Item name="search_mode" noStyle>
            <Segmented
              size="middle"
              options={[
                {
                  label: (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 8px' }}>
                      <FontSizeOutlined style={{ fontSize: 14 }} />
                      <span>按标准名称</span>
                    </div>
                  ),
                  value: 'title',
                },
                {
                  label: (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 8px' }}>
                      <FileTextOutlined style={{ fontSize: 14 }} />
                      <span>按 PDF 正文 (全文深度检索)</span>
                    </div>
                  ),
                  value: 'full_text',
                },
              ]}
              style={{
                borderRadius: 8,
                background: 'rgba(0, 96, 100, 0.05)',
                padding: '3px',
              }}
            />
          </Form.Item>
        </div>
        <Row gutter={16} align="middle">
          <Col xs={24} sm={18} md={20}>
            <Form.Item name="keyword" style={{ marginBottom: 0 }}>
              <Input
                placeholder="请输入关键词以进行模糊检索（如: Q/XMBL, 电路板）"
                prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
                allowClear
                size="large"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={6} md={4}>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              icon={<SearchOutlined />}
              size="large"
              block
              style={{
                borderRadius: 8,
                fontWeight: 500,
                background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
                borderColor: '#00acc1',
                boxShadow: '0 4px 10px rgba(0, 131, 143, 0.2)'
              }}
            >
              检索企标
            </Button>
          </Col>
        </Row>
      </Form>
    </Card>
  );
};

export default SearchForm;

