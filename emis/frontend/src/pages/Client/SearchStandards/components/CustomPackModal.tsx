import React, { useState, useEffect } from 'react';
import { Modal, Select, Radio, Form, message } from 'antd';
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
  const [selectOptions, setSelectOptions] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [parseTarget, setParseTarget] = useState('normative');

  useEffect(() => {
    if (open) {
      fetchRegions();
      form.setFieldsValue({ parse_target: 'normative' });
      setParseTarget('normative');
    }
  }, [open]);

  const fetchRegions = async () => {
    setLoading(true);
    try {
      const [provRes, cityRes] = await Promise.all([
        apiClient.get<Region[]>('/admin/dict/provinces/'),
        apiClient.get<Region[]>('/admin/dict/cities/')
      ]);
      
      const provinces = provRes.data;
      const cities = cityRes.data;
      
      const options = provinces.map(p => ({
        label: p.name,
        options: [
          { label: `${p.name} (全省)`, value: `p_${p.id}` },
          ...cities.filter(c => c.province_id === p.id).map(c => ({
            label: c.name,
            value: `c_${c.id}`,
          }))
        ]
      }));
      setSelectOptions(options);
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
    });
  };

  const handleRegionChange = (value: string[]) => {
    if (value.length > 10) {
      message.warning('最多只能选择 10 个省市地域！');
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
          label={<span style={{ fontWeight: 600, fontSize: 14 }}>选择地域 <span style={{ color: '#8c8c8c', fontSize: 12, fontWeight: 'normal' }}>(最多选择 10 个省份或城市)</span></span>}
          rules={[{ 
            required: true, 
            message: <span style={{ color: '#ff4d4f', fontWeight: 'bold' }}>请至少选择一个地域</span> 
          }]}
        >
          <Select
            mode="multiple"
            options={selectOptions}
            placeholder="请点击下拉框进行选择..."
            onChange={handleRegionChange}
            loading={loading}
            maxTagCount={10}
            style={{ width: '100%', borderRadius: 8 }}
            dropdownStyle={{ maxHeight: 400, overflow: 'auto' }}
            allowClear
          />
        </Form.Item>

        <Form.Item
          name="parse_target"
          label={<span style={{ fontWeight: 600, fontSize: 14 }}>解析需求</span>}
          rules={[{ required: true, message: '请选择解析需求' }]}
        >
          <Radio.Group 
            value={parseTarget} 
            onChange={(e) => setParseTarget(e.target.value)}
            style={{ width: '100%' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* 卡片 1 */}
              <div
                onClick={() => {
                  setParseTarget('normative');
                  form.setFieldsValue({ parse_target: 'normative' });
                }}
                style={{
                  padding: '16px 20px',
                  borderRadius: 12,
                  border: `1px solid ${parseTarget === 'normative' ? '#1890ff' : '#f0f0f0'}`,
                  background: parseTarget === 'normative' ? '#f0f7ff' : '#fafafa',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  transition: 'all 0.3s',
                  boxShadow: parseTarget === 'normative' ? '0 4px 12px rgba(24,144,255,0.08)' : 'none'
                }}
              >
                <Radio value="normative" style={{ marginTop: 4 }} />
                <div>
                  <span style={{ fontWeight: 600, fontSize: 14, color: parseTarget === 'normative' ? '#1890ff' : '#262626' }}>
                    需要进行“规范性引用解析”
                  </span>
                  <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 4, lineHeight: '1.6' }}>
                    将为您下载暂未进行过引用解析和指标解析的企标文件。
                  </div>
                </div>
              </div>

              {/* 卡片 2 */}
              <div
                onClick={() => {
                  setParseTarget('indicator');
                  form.setFieldsValue({ parse_target: 'indicator' });
                }}
                style={{
                  padding: '16px 20px',
                  borderRadius: 12,
                  border: `1px solid ${parseTarget === 'indicator' ? '#1890ff' : '#f0f0f0'}`,
                  background: parseTarget === 'indicator' ? '#f0f7ff' : '#fafafa',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  transition: 'all 0.3s',
                  boxShadow: parseTarget === 'indicator' ? '0 4px 12px rgba(24,144,255,0.08)' : 'none'
                }}
              >
                <Radio value="indicator" style={{ marginTop: 4 }} />
                <div>
                  <span style={{ fontWeight: 600, fontSize: 14, color: parseTarget === 'indicator' ? '#1890ff' : '#262626' }}>
                    需要进行“指标解析”
                  </span>
                  <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 4, lineHeight: '1.6' }}>
                    将为您下载已完成引用解析，但还未进行指标提取的企标文件。
                  </div>
                </div>
              </div>
            </div>
          </Radio.Group>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default CustomPackModal;
