import React, { useState } from 'react';
import { Form, Input, Select, Button, Card, Row, Col } from 'antd';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';
import type { CompanySearchParams } from '@/types';
import { useDictData } from '@/hooks/useDictData';

interface AdvancedSearchBarProps {
  onSearch: (values: CompanySearchParams) => void;
  loading: boolean;
}

const AdvancedSearchBar: React.FC<AdvancedSearchBarProps> = ({ onSearch, loading }) => {
  const [form] = Form.useForm();
  const [selectedProvince, setSelectedProvince] = useState<number>();
  const [selectedCity, setSelectedCity] = useState<number>();

  const { provinceQuery, useCityQuery, useDistrictQuery } = useDictData();
  const { data: cities, isLoading: citiesLoading } = useCityQuery(selectedProvince);
  const { data: districts, isLoading: districtsLoading } = useDistrictQuery(selectedCity);

  const handleFinish = (values: any) => {
    onSearch(values);
  };

  const handleReset = () => {
    form.resetFields();
    setSelectedProvince(undefined);
    setSelectedCity(undefined);
    onSearch({});
  };

  return (
    <Card 
      bordered={false} 
      style={{ 
        background: '#fff', 
        borderRadius: 12, 
        marginBottom: 24, 
        boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
        border: '1px solid #e8e8e8'
      }}
      bodyStyle={{ padding: '16px 20px' }}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
      >
        <div style={{ fontWeight: 'bold', fontSize: 13, color: '#595959', marginBottom: 12 }}>检索条件</div>

        <Row gutter={[10, 10]} align="middle">
          {/* 1. 关键词输入框 */}
          <Col xs={24} sm={24} md={7} lg={7} xl={7}>
            <Form.Item name="keyword" style={{ marginBottom: 0 }}>
              <Input 
                placeholder="企业名称 / 信用代码 / 模糊检索..." 
                prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />} 
                allowClear 
                style={{ borderRadius: 6, height: 38 }}
              />
            </Form.Item>
          </Col>

          {/* 2. 省份级联下拉 */}
          <Col xs={12} sm={12} md={4} lg={4} xl={4}>
            <Form.Item name="province_id" style={{ marginBottom: 0 }}>
              <Select
                placeholder="省份"
                style={{ width: '100%', height: 38 }}
                dropdownStyle={{ borderRadius: 6 }}
                allowClear
                onChange={(val) => {
                  setSelectedProvince(val);
                  setSelectedCity(undefined);
                  form.setFieldsValue({ city_id: undefined, district_id: undefined });
                }}
                loading={provinceQuery.isLoading}
              >
                {provinceQuery.data?.map(p => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
              </Select>
            </Form.Item>
          </Col>

          {/* 3. 城市级联下拉 */}
          <Col xs={12} sm={12} md={4} lg={4} xl={4}>
            <Form.Item name="city_id" style={{ marginBottom: 0 }}>
              <Select
                placeholder="城市"
                style={{ width: '100%', height: 38 }}
                dropdownStyle={{ borderRadius: 6 }}
                allowClear
                onChange={(val) => {
                  setSelectedCity(val);
                  form.setFieldsValue({ district_id: undefined });
                }}
                disabled={!selectedProvince}
                loading={citiesLoading}
              >
                {cities?.map(c => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}
              </Select>
            </Form.Item>
          </Col>

          {/* 4. 区县级联下拉 */}
          <Col xs={12} sm={12} md={4} lg={4} xl={4}>
            <Form.Item name="district_id" style={{ marginBottom: 0 }}>
              <Select
                placeholder="区/县"
                style={{ width: '100%', height: 38 }}
                dropdownStyle={{ borderRadius: 6 }}
                allowClear
                disabled={!selectedCity}
                loading={districtsLoading}
              >
                {districts?.map(d => <Select.Option key={d.id} value={d.id}>{d.name}</Select.Option>)}
              </Select>
            </Form.Item>
          </Col>

          {/* 5. 清空与检索操作按钮组 */}
          <Col xs={24} sm={24} md={5} lg={5} xl={5}>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', width: '100%' }}>
              <Button 
                onClick={handleReset} 
                icon={<ReloadOutlined />} 
                style={{ 
                  borderRadius: 6, 
                  height: 38, 
                  flex: 1, 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  borderColor: '#d9d9d9',
                  color: '#595959'
                }}
              >
                清空
              </Button>
              <Button 
                type="primary" 
                htmlType="submit" 
                loading={loading} 
                icon={<SearchOutlined />} 
                style={{ 
                  borderRadius: 6, 
                  height: 38, 
                  flex: 1, 
                  background: '#0b1d33', 
                  borderColor: '#0b1d33',
                  fontWeight: 'bold',
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center'
                }}
              >
                检索
              </Button>
            </div>
          </Col>
        </Row>
      </Form>
    </Card>
  );
};

export default AdvancedSearchBar;
