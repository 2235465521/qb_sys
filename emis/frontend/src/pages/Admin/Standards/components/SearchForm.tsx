import React from 'react';
import { Form, Input, Select, Button, Space, Card, Row, Col } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import type { StandardSearchParams } from '@/hooks/useStandardData';

interface SearchFormProps {
  onSearch: (values: StandardSearchParams) => void;
  loading: boolean;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, loading }) => {
  const [form] = Form.useForm();

  const handleFinish = (values: any) => {
    onSearch(values);
  };

  return (
    <Card 
      bordered={false} 
      style={{ 
        background: '#fff', 
        borderRadius: 12, 
        marginBottom: 16,
        boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
        border: '1px solid #f0f0f0'
      }}
      bodyStyle={{ padding: '16px 24px' }}
    >
      <Form
        form={form}
        layout="horizontal"
        onFinish={handleFinish}
      >
        <Row gutter={24} align="middle">
          <Col xs={24} sm={10} md={8}>
            <Form.Item name="keyword" label="标准搜索" style={{ marginBottom: 0 }}>
              <Input placeholder="标准编号 / 标准名称" prefix={<SearchOutlined />} allowClear />
            </Form.Item>
          </Col>
          <Col xs={24} sm={8} md={6}>
            <Form.Item name="status" label="标准状态" style={{ marginBottom: 0 }}>
              <Select placeholder="全部状态" allowClear style={{ width: '100%' }}>
                <Select.Option value="active">正常运行 (现行)</Select.Option>
                <Select.Option value="deprecated">已废止</Select.Option>
                <Select.Option value="draft">草案</Select.Option>
              </Select>
            </Form.Item>
          </Col>
          <Col xs={24} sm={6} md={10} style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Space size={12}>
              <Button type="primary" htmlType="submit" loading={loading} icon={<SearchOutlined />}>
                查询
              </Button>
            </Space>
          </Col>
        </Row>
      </Form>
    </Card>
  );
};

export default SearchForm;
