import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Card, Row, Col, Cascader, Select, Checkbox, Space, DatePicker } from 'antd';
import { SearchOutlined, DownOutlined, UpOutlined, ReloadOutlined } from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import apiClient from '@/api/client';
import type { Province, City, District } from '@/types';

interface SearchFormProps {
  onSearch: (params: any) => void;
  loading: boolean;
}

interface CascaderOption {
  value: string | number;
  label: string;
  isLeaf?: boolean;
  children?: CascaderOption[];
  loading?: boolean;
}

interface DateValue {
  mode: 'year' | 'date' | 'year_range' | 'date_range';
  value: Dayjs | [Dayjs, Dayjs] | null;
}

interface FlexibleDateSelectorProps {
  value?: DateValue;
  onChange?: (value: DateValue) => void;
}

const FlexibleDateSelector: React.FC<FlexibleDateSelectorProps> = ({ value, onChange }) => {
  const mode = value?.mode || 'year';
  const val = value?.value || null;

  const triggerChange = (newMode: typeof mode, newVal: typeof val) => {
    onChange?.({ mode: newMode, value: newVal });
  };

  const handleModeChange = (newMode: typeof mode) => {
    triggerChange(newMode, null);
  };

  const handleDateChange = (date: any) => {
    triggerChange(mode, date);
  };

  return (
    <Space style={{ display: 'flex', width: '100%' }}>
      <Select
        value={mode}
        onChange={handleModeChange}
        style={{ width: 110 }}
        options={[
          { value: 'year', label: '按年度' },
          { value: 'date', label: '具体日期' },
          { value: 'year_range', label: '年份范围' },
          { value: 'date_range', label: '日期范围' },
        ]}
      />
      {mode === 'year' && (
        <DatePicker
          picker="year"
          value={val as Dayjs}
          onChange={handleDateChange}
          style={{ flex: 1, width: '100%', borderRadius: 8 }}
          placeholder="选择年份"
        />
      )}
      {mode === 'date' && (
        <DatePicker
          value={val as Dayjs}
          onChange={handleDateChange}
          style={{ flex: 1, width: '100%', borderRadius: 8 }}
          placeholder="选择具体日期"
        />
      )}
      {mode === 'year_range' && (
        <DatePicker.RangePicker
          picker="year"
          value={val as [Dayjs, Dayjs]}
          onChange={handleDateChange}
          style={{ flex: 1, width: '100%', borderRadius: 8 }}
          placeholder={['开始年份', '结束年份']}
        />
      )}
      {mode === 'date_range' && (
        <DatePicker.RangePicker
          value={val as [Dayjs, Dayjs]}
          onChange={handleDateChange}
          style={{ flex: 1, width: '100%', borderRadius: 8 }}
          placeholder={['开始日期', '结束日期']}
        />
      )}
    </Space>
  );
};

const serializeDateVal = (val: DateValue | undefined) => {
  if (!val || !val.value) return { start: '', end: '' };
  const { mode, value } = val;
  if (mode === 'year' && value && !Array.isArray(value)) {
    const y = value.format('YYYY');
    return { start: y, end: y };
  }
  if (mode === 'date' && value && !Array.isArray(value)) {
    const d = value.format('YYYY-MM-DD');
    return { start: d, end: d };
  }
  if (mode === 'year_range' && Array.isArray(value) && value[0] && value[1]) {
    return { start: value[0].format('YYYY'), end: value[1].format('YYYY') };
  }
  if (mode === 'date_range' && Array.isArray(value) && value[0] && value[1]) {
    return { start: value[0].format('YYYY-MM-DD'), end: value[1].format('YYYY-MM-DD') };
  }
  return { start: '', end: '' };
};

const SearchForm: React.FC<SearchFormProps> = ({ onSearch, loading }) => {
  const [form] = Form.useForm();
  const [expanded, setExpanded] = useState(false);
  const [cascaderOptions, setCascaderOptions] = useState<CascaderOption[]>([]);

  // 首次挂载拉取省份列表
  useEffect(() => {
    const fetchProvinces = async () => {
      try {
        const { data } = await apiClient.get<Province[]>('/admin/dict/provinces/');
        setCascaderOptions(data.map(p => ({
          value: p.id,
          label: p.name,
          isLeaf: false
        })));
      } catch (err) {
        console.error('获取省份字典失败:', err);
      }
    };
    fetchProvinces();
  }, []);

  // Cascader 级联延迟加载
  const loadCascaderData = async (selectedOptions: CascaderOption[]) => {
    const targetOption = selectedOptions[selectedOptions.length - 1];
    targetOption.loading = true;

    try {
      if (selectedOptions.length === 1) {
        // 第一级：加载城市
        const { data } = await apiClient.get<City[]>('/admin/dict/cities/', {
          params: { province_id: targetOption.value }
        });
        targetOption.loading = false;
        if (data.length > 0) {
          targetOption.children = data.map(c => ({
            value: c.id,
            label: c.name,
            isLeaf: false
          }));
        } else {
          targetOption.isLeaf = true;
        }
      } else if (selectedOptions.length === 2) {
        // 第二级：加载区县
        const { data } = await apiClient.get<District[]>('/admin/dict/districts/', {
          params: { city_id: targetOption.value }
        });
        targetOption.loading = false;
        if (data.length > 0) {
          targetOption.children = data.map(d => ({
            value: d.id,
            label: d.name,
            isLeaf: true
          }));
        } else {
          targetOption.isLeaf = true;
        }
      }
      setCascaderOptions([...cascaderOptions]);
    } catch (err) {
      targetOption.loading = false;
      console.error('获取下级字典失败:', err);
    }
  };

  const handleFinish = (values: any) => {
    const params: any = {
      keyword: values.keyword,
      search_mode: values.search_mode,
      exact_match: values.exact_match
    };

    // 解析状态转换
    if (values.parse_statuses && values.parse_statuses.length > 0) {
      params.parse_status = values.parse_statuses.join(',');
    } else {
      params.parse_status = '';
    }

    if (values.region && values.region.length > 0) {
      params.province_id = values.region[0];
      if (values.region.length > 1) {
        params.city_id = values.region[1];
      }
      if (values.region.length > 2) {
        params.district_id = values.region[2];
      }
    }

    // 已发布时间序列化
    const pub = serializeDateVal(values.publishDate);
    if (pub.start && pub.end) {
      params.pub_start = pub.start;
      params.pub_end = pub.end;
    }

    // 已实施时间序列化
    const imp = serializeDateVal(values.implementDate);
    if (imp.start && imp.end) {
      params.imp_start = imp.start;
      params.imp_end = imp.end;
    }

    onSearch(params);
  };

  const handleReset = () => {
    form.resetFields();
    onSearch({
      keyword: '',
      search_mode: 'title',
      exact_match: false,
      parse_status: '',
      province_id: undefined,
      city_id: undefined,
      district_id: undefined,
      pub_start: undefined,
      pub_end: undefined,
      imp_start: undefined,
      imp_end: undefined,
    });
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
        initialValues={{ search_mode: 'title', exact_match: false, parse_statuses: [] }}
      >
        {/* 第一排 */}
        <Row gutter={16} align="middle">
          {/* 综合检索框 */}
          <Col xs={24} sm={18} md={20}>
            <Form.Item name="keyword" style={{ marginBottom: 0 }}>
              <Input
                placeholder="请输入关键词检索企业标准..."
                addonBefore={
                  <Form.Item name="search_mode" noStyle>
                    <Select style={{ width: 110, color: '#006064', fontWeight: 500 }}>
                      <Select.Option value="title">检索名称</Select.Option>
                      <Select.Option value="full_text">PDF正文</Select.Option>
                    </Select>
                  </Form.Item>
                }
                addonAfter={
                  <Form.Item name="exact_match" valuePropName="checked" noStyle>
                    <Checkbox style={{ padding: '0 8px', color: '#00838f', fontWeight: 500 }}>精确匹配</Checkbox>
                  </Form.Item>
                }
                allowClear
                size="large"
                style={{ borderRadius: 8 }}
              />
            </Form.Item>
          </Col>

          {/* 检索与高级触发组 */}
          <Col xs={24} sm={6} md={4}>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', alignItems: 'center' }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<SearchOutlined />}
                size="large"
                style={{
                  borderRadius: 8,
                  fontWeight: 500,
                  background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
                  borderColor: '#00acc1',
                  boxShadow: '0 4px 10px rgba(0, 131, 143, 0.2)',
                  flex: 1
                }}
              >
                检索
              </Button>
              <Button
                type="text"
                icon={expanded ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setExpanded(!expanded)}
                style={{ color: '#00838f', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 4 }}
              >
                高级
              </Button>
            </div>
          </Col>
        </Row>

        {/* 第二排 - 高级选项 (地域 Cascader & 解析状态) */}
        {expanded && (
          <>
            <Row gutter={16} style={{ marginTop: 16 }} align="middle">
              <Col xs={24} md={10}>
                <Form.Item label="所属地域" name="region" style={{ marginBottom: 0 }} labelCol={{ span: 5 }}>
                  <Cascader
                    options={cascaderOptions}
                    loadData={loadCascaderData}
                    placeholder="请选择省 / 市 / 区县"
                    changeOnSelect
                    size="large"
                    style={{ width: '100%', borderRadius: 8 }}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} md={14}>
                <Form.Item label="解析状态" name="parse_statuses" style={{ marginBottom: 0 }} labelCol={{ span: 5 }}>
                  <Checkbox.Group style={{ width: '100%', display: 'flex', gap: 16 }}>
                    <Checkbox value="pending_reference">待引用解析</Checkbox>
                    <Checkbox value="pending_indicator">待指标解析</Checkbox>
                  </Checkbox.Group>
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 16 }} align="middle">
              <Col xs={24} md={12}>
                <Form.Item label="发布时间" name="publishDate" style={{ marginBottom: 0 }} labelCol={{ span: 5 }}>
                  <FlexibleDateSelector />
                </Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Form.Item label="实施时间" name="implementDate" style={{ marginBottom: 0 }} labelCol={{ span: 5 }}>
                  <FlexibleDateSelector />
                </Form.Item>
              </Col>
            </Row>

            {/* 第三排 - 重置按钮 */}
            <Row gutter={[16, 16]} style={{ marginTop: 20 }} justify="end" align="middle">
              <Col xs={24} sm={6} md={4} style={{ textAlign: 'right' }}>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleReset}
                  size="large"
                  style={{ borderRadius: 8, color: '#666', width: '100%' }}
                >
                  重置
                </Button>
              </Col>
            </Row>
          </>
        )}
      </Form>
    </Card>
  );
};

export default SearchForm;
