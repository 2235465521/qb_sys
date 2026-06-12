import React, { useEffect, useState } from 'react';
import { Modal, Form, Input, Select, InputNumber, Row, Col, Tabs, Button, Spin } from 'antd';
import type { Company } from '@/types';
import { useDictData } from '@/hooks/useDictData';
import apiClient from '@/api/client';

interface ActionModalProps {
  open: boolean;
  editingRecord: Company | null;
  loading: boolean;
  isViewOnly?: boolean;
  onCancel: () => void;
  onOk: (values: Partial<Company>) => void;
}

const ActionModal: React.FC<ActionModalProps> = ({
  open,
  editingRecord,
  loading,
  isViewOnly = false,
  onCancel,
  onOk,
}) => {
  const [form] = Form.useForm();
  const [selectedProvince, setSelectedProvince] = useState<number>();
  const [selectedCity, setSelectedCity] = useState<number>();

  const { provinceQuery, useCityQuery, useDistrictQuery } = useDictData();
  const { data: cities } = useCityQuery(selectedProvince);
  const { data: districts } = useDistrictQuery(selectedCity);

  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    if (open) {
      form.resetFields();
      if (editingRecord) {
        if (editingRecord.id) {
          setLoadingDetail(true);
          apiClient.get(`/admin/companies/${editingRecord.id}/`)
            .then(res => {
              const data = res.data;
              form.setFieldsValue(data);
              if (data.province_id) setSelectedProvince(data.province_id);
              if (data.city_id) setSelectedCity(data.city_id);
            })
            .finally(() => {
              setLoadingDetail(false);
            });
        } else {
          form.setFieldsValue(editingRecord);
        }
      } else {
        setSelectedProvince(undefined);
        setSelectedCity(undefined);
      }
    }
  }, [open, editingRecord, form]);

  const handleOk = async () => {
    if (isViewOnly) {
      onCancel();
      return;
    }
    try {
      const values = await form.validateFields();
      onOk({ ...editingRecord, ...values });
    } catch (error) {
      // Validation failed
    }
  };

  const basicInfoTab = (
    <div style={{ paddingTop: 16 }}>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item
            name="name"
            label="企业名称"
            rules={[{ required: true, message: '请输入企业名称' }]}
          >
            <Input placeholder="请输入企业名称" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item
            name="credit_code"
            label="统一社会信用代码"
            rules={[{ required: true, message: '请输入统一社会信用代码' }]}
          >
            <Input placeholder="请输入信用代码" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="province_id" label="省份" rules={[{ required: true, message: '请选择省份' }]}>
            <Select
              placeholder="请选择省份"
              onChange={(val) => {
                setSelectedProvince(val);
                form.setFieldsValue({ city_id: undefined, district_id: undefined });
              }}
            >
              {provinceQuery.data?.map(p => <Select.Option key={p.id} value={p.id}>{p.name}</Select.Option>)}
            </Select>
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="city_id" label="城市" rules={[{ required: true, message: '请选择城市' }]}>
            <Select
              placeholder="请选择城市"
              disabled={!selectedProvince}
              onChange={(val) => {
                setSelectedCity(val);
                form.setFieldsValue({ district_id: undefined });
              }}
            >
              {cities?.map(c => <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>)}
            </Select>
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="district_id" label="区县" rules={[{ required: true, message: '请选择区县' }]}>
            <Select placeholder="请选择区县" disabled={!selectedCity}>
              {districts?.map(d => <Select.Option key={d.id} value={d.id}>{d.name}</Select.Option>)}
            </Select>
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="legal_person" label="法人">
            <Input placeholder="请输入法人姓名" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="contact" label="联系方式">
            <Input placeholder="电话/手机号" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select>
              <Select.Option value="active">正常</Select.Option>
              <Select.Option value="disabled">禁用</Select.Option>
            </Select>
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="latitude" label="纬度 (Latitude)">
            <InputNumber style={{ width: '100%' }} precision={7} placeholder="如: 39.9042" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="longitude" label="经度 (Longitude)">
            <InputNumber style={{ width: '100%' }} precision={7} placeholder="如: 116.4074" />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item name="address" label="详细地址 (业务/经营地址)">
        <Input placeholder="请输入详细地址信息" />
      </Form.Item>
    </div>
  );

  const advancedInfoTab = (
    <div style={{ paddingTop: 16 }}>
      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="english_name" label="英文名">
            <Input placeholder="请输入英文名" />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="former_names" label="曾用名">
            <Input placeholder="曾用名（若有）" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="established_date" label="成立日期">
            <Input type="date" placeholder="成立日期" style={{ width: '100%' }} />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="company_type" label="企业(机构)类型">
            <Input placeholder="如：有限责任公司" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="company_size" label="企业规模">
            <Select placeholder="选择企业规模">
              <Select.Option value="大型">大型</Select.Option>
              <Select.Option value="中型">中型</Select.Option>
              <Select.Option value="小型">小型</Select.Option>
              <Select.Option value="微型">微型</Select.Option>
            </Select>
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="valid_mobile" label="有效手机号">
            <Input placeholder="有效联系手机" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="more_phones" label="更多电话">
            <Input placeholder="其他电话，分号隔开" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '请输入合法的邮箱地址' }]}>
            <Input placeholder="企业邮箱" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Form.Item name="website_url" label="企业官网">
            <Input placeholder="http://..." />
          </Form.Item>
        </Col>
        <Col span={12}>
          <Form.Item name="registration_status" label="登记状态">
            <Input placeholder="如：存续、在营、注销" />
          </Form.Item>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={8}>
          <Form.Item name="registration_no" label="注册号">
            <Input placeholder="工商注册号" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="organization_code" label="组织机构代码">
            <Input placeholder="组织机构代码" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="registered_zipcode" label="注册地址邮编">
            <Input placeholder="邮政编码" />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item name="registered_address" label="注册地址 (营业执照所在地址)">
        <Input placeholder="请输入营业执照上的注册地址" />
      </Form.Item>

      <Row gutter={16}>
        <Col span={16}>
          <Form.Item name="mailing_address" label="通讯地址">
            <Input placeholder="请输入通讯地址" />
          </Form.Item>
        </Col>
        <Col span={8}>
          <Form.Item name="mailing_address_zip" label="通讯邮编">
            <Input placeholder="通讯地址邮编" />
          </Form.Item>
        </Col>
      </Row>

      <Form.Item name="business_scope" label="经营范围">
        <Input.TextArea rows={3} placeholder="请输入经营范围" />
      </Form.Item>

      <Row gutter={16}>
        <Col span={6}>
          <Form.Item name="industry_category" label="国标行业门类">
            <Input placeholder="行业门类" />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item name="industry_major" label="国标行业大类">
            <Input placeholder="行业大类" />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item name="industry_middle" label="国标行业中类">
            <Input placeholder="行业中类" />
          </Form.Item>
        </Col>
        <Col span={6}>
          <Form.Item name="industry_minor" label="国标行业小类">
            <Input placeholder="行业小类" />
          </Form.Item>
        </Col>
      </Row>
    </div>
  );

  const tabItems = [
    { label: '基础与位置信息', key: 'basic', children: basicInfoTab },
    { label: '详细与分类信息', key: 'advanced', children: advancedInfoTab },
  ];

  return (
    <Modal
      title={isViewOnly ? '企业详情' : (editingRecord ? '编辑企业' : '新增企业')}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      width={780}
      maskClosable={false}
      destroyOnClose
      footer={isViewOnly ? [
        <Button key="close" type="primary" onClick={onCancel}>关闭</Button>
      ] : undefined}
    >
      <Spin spinning={loadingDetail} tip="正在加载企业详情数据...">
        {isViewOnly && (
          <style>
            {`
              .ant-input-disabled, 
              .ant-input-number-disabled, 
              .ant-select-disabled .ant-select-selector,
              .ant-picker-disabled {
                background-color: transparent !important;
                border-color: transparent !important;
                color: rgba(0, 0, 0, 0.85) !important;
                cursor: default !important;
              }
              .ant-select-disabled .ant-select-arrow {
                display: none;
              }
            `}
          </style>
        )}
        <Form form={form} layout="vertical" initialValues={{ status: 'active' }} disabled={isViewOnly}>
          <Tabs defaultActiveKey="basic" items={tabItems} />
        </Form>
      </Spin>
    </Modal>
  );
};

export default ActionModal;
