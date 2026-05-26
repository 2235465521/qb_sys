import React from 'react';
import { Form, Input, Button, Card, Row, Col } from 'antd';
import { SearchOutlined } from '@ant-design/icons';

interface SearchFormProps {
  onSearch: (keyword: string) => void;
  loading: boolean;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, loading }) => {
  const [form] = Form.useForm();

  const handleFinish = (values: any) => {
    onSearch(values.keyword || '');
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
      >
        <Row gutter={24} align="middle">
          <Col xs={24} sm={18} md={20}>
            <Form.Item name="keyword" style={{ marginBottom: 0 }}>
              <Input
                placeholder="请输入标准编号或标准名称以进行模糊检索（如: Q/XMBL, 电路板）"
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
              style={{ borderRadius: 8, fontWeight: 500 }}
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
