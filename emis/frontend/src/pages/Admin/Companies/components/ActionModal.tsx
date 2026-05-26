import React, { useEffect, useState } from 'react';
import { Modal, Form, Input, Select, InputNumber, Row, Col } from 'antd';
import type { Company } from '@/types';
import { useDictData } from '@/hooks/useDictData';

interface ActionModalProps {
  open: boolean;
  editingRecord: Company | null;
  loading: boolean;
  onCancel: () => void;
  onOk: (values: Partial<Company>) => void;
}

const ActionModal: React.FC<ActionModalProps> = ({
  open,
  editingRecord,
  loading,
  onCancel,
  onOk,
}) => {
  const [form] = Form.useForm();
  const [selectedProvince, setSelectedProvince] = useState<number>();
  const [selectedCity, setSelectedCity] = useState<number>();

  const { provinceQuery, useCityQuery, useDistrictQuery } = useDictData();
  const { data: cities } = useCityQuery(selectedProvince);
  const { data: districts } = useDistrictQuery(selectedCity);

  useEffect(() => {
    if (open) {
      if (editingRecord) {
        form.setFieldsValue(editingRecord);
        // 初始化联动状态
        if (editingRecord.province_id) setSelectedProvince(editingRecord.province_id as unknown as number);
        if (editingRecord.city_id) setSelectedCity(editingRecord.city_id as unknown as number);
      } else {
        form.resetFields();
        setSelectedProvince(undefined);
        setSelectedCity(undefined);
      }
    }
  }, [open, editingRecord, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      onOk({ ...editingRecord, ...values });
    } catch (error) {
      // Validation failed
    }
  };

  return (
    <Modal
      title={editingRecord ? '编辑企业' : '新增企业'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={loading}
      width={720}
      maskClosable={false}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ status: 'active' }}>
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
            <Form.Item name="province_id" label="省份" rules={[{ required: true }]}>
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
            <Form.Item name="city_id" label="城市" rules={[{ required: true }]}>
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
            <Form.Item name="district_id" label="区县" rules={[{ required: true }]}>
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

        <Form.Item name="address" label="详细地址">
          <Input.TextArea rows={2} placeholder="请输入详细经营地址" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ActionModal;
