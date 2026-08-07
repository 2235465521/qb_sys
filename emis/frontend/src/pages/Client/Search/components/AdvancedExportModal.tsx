import React, { useState, useEffect } from 'react';
import { Modal, Form, Radio, Checkbox, Select, Segmented, Space, Typography, message, Alert, Divider } from 'antd';
import { ExportOutlined, FilterOutlined, FileExcelOutlined, FileZipOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';
import { useDictData } from '@/hooks/useDictData';
import type { CompanySearchParams, Company } from '@/types';

const { Text } = Typography;

const AGENCY_TYPE_OPTIONS = [
  '有限责任公司',
  '一人有限责任公司',
  '其他有限责任公司',
  '股份有限公司',
  '个体工商户',
  '农民专业合作社(联合社)',
  '个人独资企业',
  '社会组织',
  '社会团体',
  '民办非企业单位',
  '基金会',
  '其他社会组织',
  '普通合伙',
  '事业单位',
  '有限合伙',
  '机关单位',
  '全民所有制',
  '集体所有制',
  '联营企业',
  '股份合作企业',
  '农村集体经济组织',
  '基层群众性自治组织',
];


interface AdvancedExportModalProps {
  visible: boolean;
  onCancel: () => void;
  selectedEnterprises: Company[];
  searchParams: CompanySearchParams;
  totalFilteredCount: number;
  onDispatchTask: (taskId: string, title: string, hasDownload: boolean, typeUrl: string, payload: any) => void;
}

export const AdvancedExportModal: React.FC<AdvancedExportModalProps> = ({
  visible,
  onCancel,
  selectedEnterprises,
  searchParams,
  totalFilteredCount,
  onDispatchTask,
}) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [exportScope, setExportScope] = useState<'selected' | 'filtered'>(
    selectedEnterprises.length > 0 ? 'selected' : 'filtered'
  );
  const [agencyMode, setAgencyMode] = useState<'include' | 'exclude'>('include');

  const [selectedProvince, setSelectedProvince] = useState<number | undefined>(
    searchParams.province_id ? Number(searchParams.province_id) : undefined
  );
  const [selectedCity, setSelectedCity] = useState<number | undefined>(
    searchParams.city_id ? Number(searchParams.city_id) : undefined
  );

  const { provinceQuery, useCityQuery, useDistrictQuery } = useDictData();
  const { data: cities } = useCityQuery(selectedProvince);
  const { data: districts } = useDistrictQuery(selectedCity);

  useEffect(() => {
    if (visible) {
      const scope = selectedEnterprises.length > 0 ? 'selected' : 'filtered';
      setExportScope(scope);
      setSelectedProvince(searchParams.province_id ? Number(searchParams.province_id) : undefined);
      setSelectedCity(searchParams.city_id ? Number(searchParams.city_id) : undefined);

      form.setFieldsValue({
        export_scope: scope,
        agency_type_mode: 'include',
        agency_types: [],
        province_id: searchParams.province_id ? Number(searchParams.province_id) : undefined,
        city_id: searchParams.city_id ? Number(searchParams.city_id) : undefined,
        district_id: searchParams.district_id ? Number(searchParams.district_id) : undefined,
        export_content: ['enterprise', 'enterprise_standard', 'other_standard'],
        file_format: 'single_excel',
      });
    }
  }, [visible, selectedEnterprises, searchParams]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (!values.export_content || values.export_content.length === 0) {
        message.warning('请至少选择一项要导出的内容');
        return;
      }

      setLoading(true);

      const payload: any = {
        export_scope: values.export_scope,
        export_content: values.export_content,
        file_format: values.export_content.length > 1 ? values.file_format : 'single_excel',
        advanced_filters: {
          agency_type_mode: values.agency_type_mode,
          agency_types: values.agency_types || [],
        },
      };

      if (values.export_scope === 'selected') {
        payload.enterprise_ids = selectedEnterprises.map(c => c.id);
      } else {
        const { keyword } = searchParams;
        payload.base_filters = {
          q: keyword,
          province_id: values.province_id,
          city_id: values.city_id,
          district_id: values.district_id,
        };
      }


      const { data } = await apiClient.post<{ task_id: string; message: string }>(
        '/client/standards/export-advanced/',
        payload
      );

      message.success('已成功分发高级导出任务！您可在右上角任务中心查看进度');
      onDispatchTask(data.task_id, '企业与企标高级导出', true, '/client/standards/export-advanced/', payload);
      onCancel();
    } catch (err: any) {
      if (err.response) {
        message.error(err.response.data?.error || '分发任务请求失败');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 600 }}>
          <ExportOutlined style={{ color: '#0d9488' }} />
          高级导出企业与标准目录
        </div>
      }
      open={visible}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={loading}
      okText="开始导出"
      cancelText="取消"
      width={650}
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 12 }}>
        {/* 1. 导出范围 */}
        <Form.Item name="export_scope" label={<Text strong>1. 选择导出范围</Text>}>
          <Radio.Group onChange={e => setExportScope(e.target.value)}>
            <Radio value="selected" disabled={selectedEnterprises.length === 0}>
              勾选的企业 ({selectedEnterprises.length} 家)
            </Radio>
            <Radio value="filtered">
              检索结果全部匹配企业 ({totalFilteredCount} 家)
            </Radio>
          </Radio.Group>
        </Form.Item>

        <Divider style={{ margin: '12px 0' }} />

        {/* 2. 机构类型包含/排除模式 */}
        <Form.Item
          label={
            <Space>
              <Text strong>2. 企业(机构)类型筛选</Text>
              <FilterOutlined style={{ color: '#8c8c8c' }} />
            </Space>
          }
        >
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Form.Item name="agency_type_mode" noStyle>
              <Segmented
                options={[
                  { label: '包含指定类型', value: 'include' },
                  { label: '排除某些类型', value: 'exclude' },
                ]}
                onChange={val => setAgencyMode(val as any)}
              />
            </Form.Item>

            <Form.Item name="agency_types" noStyle>
              <Checkbox.Group options={AGENCY_TYPE_OPTIONS} style={{ width: '100%', gap: '8px 16px' }} />
            </Form.Item>

            <Text type="secondary" style={{ fontSize: 12 }}>
              {agencyMode === 'include'
                ? '提示：若不勾选任何类型，默认包含全部企业/机构类型'
                : '提示：选中的类型将被剔除，导出的数据中将不包含这些机构'}
            </Text>
          </Space>
        </Form.Item>

        {/* 3. 行政区划联动 (全选模式下开启) */}
        {exportScope === 'filtered' && (
          <Form.Item label={<Text strong>3. 行政区划筛选（省市县）</Text>}>
            <Space style={{ width: '100%' }} size={8}>
              <Form.Item name="province_id" noStyle>
                <Select
                  placeholder="选择省份"
                  allowClear
                  options={provinceQuery.data?.map(p => ({ label: p.name, value: p.id }))}
                  onChange={val => {
                    setSelectedProvince(val);
                    setSelectedCity(undefined);
                    form.setFieldsValue({ city_id: undefined, district_id: undefined });
                  }}
                  style={{ width: 140 }}
                />
              </Form.Item>

              <Form.Item name="city_id" noStyle>
                <Select
                  placeholder="选择城市"
                  allowClear
                  options={cities?.map(c => ({ label: c.name, value: c.id }))}
                  onChange={val => {
                    setSelectedCity(val);
                    form.setFieldsValue({ district_id: undefined });
                  }}
                  style={{ width: 140 }}
                />
              </Form.Item>

              <Form.Item name="district_id" noStyle>
                <Select
                  placeholder="选择区县"
                  allowClear
                  options={districts?.map(d => ({ label: d.name, value: d.id }))}
                  style={{ width: 140 }}
                />
              </Form.Item>
            </Space>
          </Form.Item>
        )}

        <Divider style={{ margin: '12px 0' }} />

        {/* 4. 导出内容选择 (多选) */}
        <Form.Item name="export_content" label={<Text strong>4. 导出内容选择（可多选）</Text>}>
          <Checkbox.Group
            options={[
              { label: '企业目录', value: 'enterprise' },
              { label: '企标目录（自动去重）', value: 'enterprise_standard' },
              { label: '国/行/地/团标目录（自动去重）', value: 'other_standard' },
            ]}
            style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
          />
        </Form.Item>

        <Form.Item name="file_format" label={<Text strong>5. 文件输出方式</Text>}>
          <Radio.Group style={{ width: '100%' }}>
            <Space direction="vertical">
              <Radio value="single_excel">
                <Space>
                  <FileExcelOutlined style={{ color: '#52c41a' }} />
                  <span>单 Excel 文件（自动按已选内容分设多个 Sheet 工作表）</span>
                </Space>
              </Radio>
              <Radio value="separate_zip">
                <Space>
                  <FileZipOutlined style={{ color: '#1890ff' }} />
                  <span>打包压缩包 ZIP（将勾选的目录拆分为独立 Excel 文件打包）</span>
                </Space>
              </Radio>
            </Space>
          </Radio.Group>
        </Form.Item>

        <Alert
          message="说明：导出的标准目录包含企标以及企业关联/引用的国行地团标，全局自动按标准号去重。"
          type="info"
          showIcon
          style={{ borderRadius: 8, marginTop: 8 }}
        />
      </Form>
    </Modal>
  );
};

