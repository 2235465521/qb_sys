import React, { useState, useEffect } from 'react';
import { Modal, TreeSelect, Radio, Form, message } from 'antd';
import apiClient from '@/api/client';

interface Region {
  id: number;
  code: string;
  name: string;
  province_id?: number;
}

interface CustomPackModalProps {
  open: boolean;
  onCancel: () => void;
  onSubmit: (params: { province_ids: number[], city_ids: number[], parse_target: string }) => void;
}

const CustomPackModal: React.FC<CustomPackModalProps> = ({ open, onCancel, onSubmit }) => {
  const [form] = Form.useForm();
  const [treeData, setTreeData] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && treeData.length === 0) {
      fetchRegions();
    }
  }, [open, treeData.length]);

  const fetchRegions = async () => {
    setLoading(true);
    try {
      const [provRes, cityRes] = await Promise.all([
        apiClient.get<Region[]>('/admin/dict/provinces/'),
        apiClient.get<Region[]>('/admin/dict/cities/')
      ]);
      
      const provinces = provRes.data;
      const cities = cityRes.data;
      
      const data = provinces.map(p => ({
        title: p.name,
        value: `p_${p.id}`,
        key: `p_${p.id}`,
        children: cities.filter(c => c.province_id === p.id).map(c => ({
          title: c.name,
          value: `c_${c.id}`,
          key: `c_${c.id}`,
        }))
      }));
      setTreeData(data);
    } catch (err) {
      message.error('获取地域数据失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  const handleOk = () => {
    form.validateFields().then(values => {
      const selectedNodes: string[] = values.regions || [];
      const province_ids = selectedNodes.filter(v => v.startsWith('p_')).map(v => parseInt(v.split('_')[1]));
      const city_ids = selectedNodes.filter(v => v.startsWith('c_')).map(v => parseInt(v.split('_')[1]));
      
      onSubmit({
        province_ids,
        city_ids,
        parse_target: values.parse_target
      });
      // 不要在这里 resetFields，让外层通过 onCancel 来控制或下次打开时状态依旧
    });
  };

  const handleRegionChange = (value: string[]) => {
    if (value.length > 10) {
      message.warning('最多只能选择 10 个省市节点！');
      form.setFieldsValue({ regions: value.slice(0, 10) });
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#006064' }}>
          <span style={{ fontWeight: 'bold', fontSize: 16 }}>自定义选择下载</span>
        </div>
      }
      open={open}
      onCancel={onCancel}
      onOk={handleOk}
      okText="确定打包"
      cancelText="取消"
      width={520}
      centered
      bodyStyle={{ padding: '24px 0' }}
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{ parse_target: 'normative' }}
      >
        <Form.Item
          name="regions"
          label={<span style={{ fontWeight: 500 }}>选择地域 <span style={{ color: '#8c8c8c', fontSize: 13, fontWeight: 'normal' }}>(最多选择 10 个省份或城市)</span></span>}
          rules={[{ required: true, message: '请至少选择一个地域' }]}
        >
          <TreeSelect
            treeData={treeData}
            treeCheckable={true}
            showCheckedStrategy={TreeSelect.SHOW_PARENT}
            placeholder="请点击下拉框进行选择..."
            onChange={handleRegionChange}
            loading={loading}
            maxTagCount={10}
            style={{ width: '100%' }}
            dropdownStyle={{ maxHeight: 400, overflow: 'auto' }}
            allowClear
          />
        </Form.Item>

        <Form.Item
          name="parse_target"
          label={<span style={{ fontWeight: 500 }}>解析需求</span>}
          rules={[{ required: true, message: '请选择解析需求' }]}
        >
          <Radio.Group style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Radio value="normative" style={{ padding: '8px 12px', background: '#fafafa', borderRadius: 6, border: '1px solid #f0f0f0' }}>
              <span style={{ fontWeight: 'bold' }}>需要进行“规范性引用解析”</span>
              <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 4 }}>
                将为您下载暂未进行过引用解析和指标解析的企标文件。
              </div>
            </Radio>
            <Radio value="indicator" style={{ padding: '8px 12px', background: '#fafafa', borderRadius: 6, border: '1px solid #f0f0f0' }}>
              <span style={{ fontWeight: 'bold' }}>需要进行“指标解析”</span>
              <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 4 }}>
                将为您下载已完成引用解析，但还未进行指标提取的企标文件。
              </div>
            </Radio>
          </Radio.Group>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default CustomPackModal;
