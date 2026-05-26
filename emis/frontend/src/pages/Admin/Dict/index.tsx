import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Input, List, Typography, Space, Spin, Empty, Tag, Alert } from 'antd';
import { GlobalOutlined, RightOutlined, ApartmentOutlined, InfoCircleOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';

const { Title, Paragraph, Text } = Typography;

interface DictItem {
  id: number;
  code: string;
  name: string;
}

interface CityItem extends DictItem {
  province_id: number;
}

interface DistrictItem extends DictItem {
  city_id: number;
}

const DictPage: React.FC = () => {
  const [selectedProv, setSelectedProv] = useState<DictItem | null>(null);
  const [selectedCity, setSelectedCity] = useState<DictItem | null>(null);

  const [provSearch, setProvSearch] = useState('');
  const [citySearch, setCitySearch] = useState('');
  const [distSearch, setDistSearch] = useState('');

  // 1. 获取所有省份
  const { data: provinces = [], isLoading: provLoading } = useQuery<DictItem[]>({
    queryKey: ['dictProvinces'],
    queryFn: async () => {
      const { data } = await apiClient.get<DictItem[]>('/admin/dict/provinces/');
      return data;
    }
  });

  // 2. 根据省份获取地级市
  const { data: cities = [], isLoading: cityLoading } = useQuery<CityItem[]>({
    queryKey: ['dictCities', selectedProv?.id],
    queryFn: async () => {
      if (!selectedProv) return [];
      const { data } = await apiClient.get<CityItem[]>(`/admin/dict/cities/?province_id=${selectedProv.id}`);
      return data;
    },
    enabled: !!selectedProv
  });

  // 3. 根据城市获取区县
  const { data: districts = [], isLoading: distLoading } = useQuery<DistrictItem[]>({
    queryKey: ['dictDistricts', selectedCity?.id],
    queryFn: async () => {
      if (!selectedCity) return [];
      const { data } = await apiClient.get<DistrictItem[]>(`/admin/dict/districts/?city_id=${selectedCity.id}`);
      return data;
    },
    enabled: !!selectedCity
  });

  // 列表本地实时搜索过滤
  const filteredProvinces = provinces.filter(p => 
    p.name.includes(provSearch) || p.code.includes(provSearch)
  );

  const filteredCities = cities.filter(c => 
    c.name.includes(citySearch) || c.code.includes(citySearch)
  );

  const filteredDistricts = districts.filter(d => 
    d.name.includes(distSearch) || d.code.includes(distSearch)
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* 头部介绍区域 */}
      <div style={{ background: '#fff', padding: 24, borderRadius: 16, border: '1px solid #f0f0f0', boxShadow: '0 4px 20px rgba(0,0,0,0.02)' }}>
        <Title level={3} style={{ margin: 0, fontWeight: 'bold' }}>行政区划数据字典</Title>
        <Paragraph type="secondary" style={{ margin: '8px 0 0 0' }}>
          维护并查询平台全局所使用的省、市、区（县）三级行政区划字典。该字典被“企业库管理”和“前台高级 LBS 区域检索”高度依赖，用以提供规范的地理筛选和标准化的企业地理归属设定。
        </Paragraph>
      </div>

      <Row gutter={[24, 24]}>
        {/* 省份卡片 */}
        <Col xs={24} md={8}>
          <Card 
            title={<Space><GlobalOutlined style={{ color: '#1890ff' }} /> <span>省级行政区 ({filteredProvinces.length})</span></Space>}
            style={{ borderRadius: 16, border: '1px solid #f0f0f0', boxShadow: '0 4px 20px rgba(0,0,0,0.04)', height: 600, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          >
            <Input.Search 
              placeholder="搜索省份名称/邮编" 
              value={provSearch}
              onChange={e => setProvSearch(e.target.value)}
              allowClear
              style={{ marginBottom: 12 }}
            />
            {provLoading ? (
              <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Spin /></div>
            ) : filteredProvinces.length === 0 ? (
              <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Empty description="暂无省份数据" /></div>
            ) : (
              <div style={{ flex: 1, overflowY: 'auto' }}>
                <List
                  dataSource={filteredProvinces}
                  renderItem={item => {
                    const isSelected = selectedProv?.id === item.id;
                    return (
                      <List.Item 
                        onClick={() => {
                          setSelectedProv(item);
                          setSelectedCity(null);
                          setCitySearch('');
                          setDistSearch('');
                        }}
                        style={{
                          padding: '12px 16px',
                          borderRadius: 8,
                          cursor: 'pointer',
                          backgroundColor: isSelected ? '#e6f7ff' : 'transparent',
                          border: isSelected ? '1px solid #91d5ff' : '1px solid transparent',
                          marginBottom: 4,
                          transition: 'all 0.2s',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <Space direction="vertical" size={2}>
                          <Text style={{ fontWeight: isSelected ? 'bold' : 500, color: isSelected ? '#1890ff' : '#333' }}>{item.name}</Text>
                          <Tag color="blue" bordered={false} style={{ fontSize: 10, margin: 0 }}>{item.code}</Tag>
                        </Space>
                        <RightOutlined style={{ fontSize: 12, color: isSelected ? '#1890ff' : '#bfbfbf' }} />
                      </List.Item>
                    );
                  }}
                />
              </div>
            )}
          </Card>
        </Col>

        {/* 城市卡片 */}
        <Col xs={24} md={8}>
          <Card 
            title={<Space><ApartmentOutlined style={{ color: '#52c41a' }} /> <span>市级地级市 ({selectedProv ? filteredCities.length : 0})</span></Space>}
            style={{ borderRadius: 16, border: '1px solid #f0f0f0', boxShadow: '0 4px 20px rgba(0,0,0,0.04)', height: 600, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          >
            {!selectedProv ? (
              <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <Empty description="请在左侧选择省份" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : (
              <>
                <Input.Search 
                  placeholder={`搜索 ${selectedProv.name} 内的城市`} 
                  value={citySearch}
                  onChange={e => setCitySearch(e.target.value)}
                  allowClear
                  style={{ marginBottom: 12 }}
                />
                {cityLoading ? (
                  <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Spin /></div>
                ) : filteredCities.length === 0 ? (
                  <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Empty description="该省份下无地级市数据" /></div>
                ) : (
                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    <List
                      dataSource={filteredCities}
                      renderItem={item => {
                        const isSelected = selectedCity?.id === item.id;
                        return (
                          <List.Item 
                            onClick={() => {
                              setSelectedCity(item);
                              setDistSearch('');
                            }}
                            style={{
                              padding: '12px 16px',
                              borderRadius: 8,
                              cursor: 'pointer',
                              backgroundColor: isSelected ? '#f6ffed' : 'transparent',
                              border: isSelected ? '1px solid #b7eb8f' : '1px solid transparent',
                              marginBottom: 4,
                              transition: 'all 0.2s',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center'
                            }}
                          >
                            <Space direction="vertical" size={2}>
                              <Text style={{ fontWeight: isSelected ? 'bold' : 500, color: isSelected ? '#52c41a' : '#333' }}>{item.name}</Text>
                              <Tag color="green" bordered={false} style={{ fontSize: 10, margin: 0 }}>{item.code}</Tag>
                            </Space>
                            <RightOutlined style={{ fontSize: 12, color: isSelected ? '#52c41a' : '#bfbfbf' }} />
                          </List.Item>
                        );
                      }}
                    />
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>

        {/* 区县卡片 */}
        <Col xs={24} md={8}>
          <Card 
            title={<Space><ApartmentOutlined style={{ color: '#faad14' }} /> <span>区县/县级市 ({selectedCity ? filteredDistricts.length : 0})</span></Space>}
            style={{ borderRadius: 16, border: '1px solid #f0f0f0', boxShadow: '0 4px 20px rgba(0,0,0,0.04)', height: 600, display: 'flex', flexDirection: 'column' }}
            bodyStyle={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          >
            {!selectedCity ? (
              <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <Empty description="请在左侧选择城市" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              </div>
            ) : (
              <>
                <Input.Search 
                  placeholder={`搜索 ${selectedCity.name} 内的区县`} 
                  value={distSearch}
                  onChange={e => setDistSearch(e.target.value)}
                  allowClear
                  style={{ marginBottom: 12 }}
                />
                {distLoading ? (
                  <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Spin /></div>
                ) : filteredDistricts.length === 0 ? (
                  <div style={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}><Empty description="该城市下无区县数据" /></div>
                ) : (
                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    <List
                      dataSource={filteredDistricts}
                      renderItem={item => (
                        <List.Item 
                          style={{
                            padding: '12px 16px',
                            borderRadius: 8,
                            backgroundColor: '#fffbe6',
                            border: '1px solid #ffe58f',
                            marginBottom: 4,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}
                        >
                          <Space direction="vertical" size={2}>
                            <Text style={{ fontWeight: 500, color: '#d46b08' }}>{item.name}</Text>
                            <Tag color="orange" bordered={false} style={{ fontSize: 10, margin: 0 }}>{item.code}</Tag>
                          </Space>
                        </List.Item>
                      )}
                    />
                  </div>
                )}
              </>
            )}
          </Card>
        </Col>
      </Row>

      {/* 说明栏 */}
      <Alert 
        message="行政区划配置说明"
        description="所有数据字典数据完全在后端预设并支持数据库缓存，确保毫秒级三级级联响应。在“企业库管理”模块录入企业时，系统会自动调用该接口渲染地理位置选择器，用以提供规范合规的数据信息录入。"
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        style={{ borderRadius: 12 }}
      />
    </div>
  );
};

export default DictPage;
