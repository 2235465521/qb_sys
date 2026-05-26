import React, { useState } from 'react';
import { Form, Input, Select, Button, Space, Card } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import type { CompanySearchParams } from '@/types';
import { useDictData } from '@/hooks/useDictData';

interface SearchFormProps {
  onSearch: (values: CompanySearchParams) => void;
  onReset: () => void;
  loading?: boolean;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, onReset, loading }) => {
  const [form] = Form.useForm();
  const [selectedProvince, setSelectedProvince] = useState<number>();
  const [selectedCity, setSelectedCity] = useState<number>();

  const { provinceQuery, useCityQuery, useDistrictQuery } = useDictData();
  const { data: cities } = useCityQuery(selectedProvince);
  const { data: districts } = useDistrictQuery(selectedCity);

  const handleFinish = (values: any) => {
    onSearch(values);
  };

  const handleReset = () => {
    form.resetFields();
    setSelectedProvince(undefined);
    setSelectedCity(undefined);
    onReset();
  };

  return (
    <Card style={{ marginBottom: 16 }}>
      <Form
        form={form}
        layout="inline"
        onFinish={handleFinish}
        initialValues={{ status: 'active' }}
      >
        <Form.Item name="province_id" label="区域">
          <Select
            placeholder="省"
            style={{ width: 120 }}
            allowClear
            onChange={(val) => {
              setSelectedProvince(val);
              form.setFieldsValue({ city_id: undefined, district_id: undefined });
            }}
            loading={provinceQuery.isLoading}
          >
            {provinceQuery.data?.map(p => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="city_id">
          <Select
            placeholder="市"
            style={{ width: 120 }}
            allowClear
            onChange={(val) => {
              setSelectedCity(val);
              form.setFieldsValue({ district_id: undefined });
            }}
            disabled={!selectedProvince}
          >
            {cities?.map(c => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="district_id">
          <Select
            placeholder="区/县"
            style={{ width: 120 }}
            allowClear
            disabled={!selectedCity}
          >
            {districts?.map(d => <Select.Option key={d.id} value={d.id}>{d.name}</Select.Option>)}
          </Select>
        </Form.Item>
        <Form.Item name="keyword" label="关键字">
          <Input placeholder="企业名称 / 信用代码" allowClear style={{ width: 180 }} />
        </Form.Item>
        <Form.Item name="status" label="状态">
          <Select style={{ width: 120 }}>
            <Select.Option value="">全部</Select.Option>
            <Select.Option value="active">正常</Select.Option>
            <Select.Option value="disabled">禁用</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} htmlType="submit" loading={loading}>
              查询
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default SearchForm;
