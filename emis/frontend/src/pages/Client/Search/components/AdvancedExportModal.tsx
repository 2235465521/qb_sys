import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Radio,
  Checkbox,
  Select,
  Segmented,
  Space,
  Typography,
  message,
  Alert,
  Divider,
  Input,
  Tag,
  Tooltip,
} from 'antd';
import {
  ExportOutlined,
  FilterOutlined,
  FileExcelOutlined,
  FileZipOutlined,
  BankOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
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

const PREF_STORAGE_KEY = 'emis_advanced_export_preferences';

interface AdvancedExportPreferences {
  agency_type_mode?: 'include' | 'exclude';
  agency_types?: string[];
  export_content?: string[];
  file_format?: 'single_excel' | 'separate_zip';
  reg_level?: string;
  reg_authority?: string;
}

const loadExportPreferences = (): AdvancedExportPreferences => {
  try {
    const raw = localStorage.getItem(PREF_STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (e) {
    console.warn('Failed to load export preferences:', e);
  }
  return {};
};

const saveExportPreferences = (prefs: AdvancedExportPreferences) => {
  try {
    localStorage.setItem(PREF_STORAGE_KEY, JSON.stringify(prefs));
  } catch (e) {
    console.warn('Failed to save export preferences:', e);
  }
};

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
  const selectedDistrict = Form.useWatch('district_id', form);

  const currentProvinceObj = provinceQuery.data?.find(p => p.id === selectedProvince);
  const currentCityObj = cities?.find(c => c.id === selectedCity);
  const currentDistrictObj = districts?.find(d => d.id === selectedDistrict);

  useEffect(() => {
    if (visible) {
      const scope = selectedEnterprises.length > 0 ? 'selected' : 'filtered';
      setExportScope(scope);
      setSelectedProvince(searchParams.province_id ? Number(searchParams.province_id) : undefined);
      setSelectedCity(searchParams.city_id ? Number(searchParams.city_id) : undefined);

      const savedPrefs = loadExportPreferences();
      const mode = savedPrefs.agency_type_mode || 'include';
      setAgencyMode(mode);

      form.setFieldsValue({
        export_scope: scope,
        agency_type_mode: mode,
        agency_types: savedPrefs.agency_types || [],
        province_id: searchParams.province_id ? Number(searchParams.province_id) : undefined,
        city_id: searchParams.city_id ? Number(searchParams.city_id) : undefined,
        district_id: searchParams.district_id ? Number(searchParams.district_id) : undefined,
        reg_level: savedPrefs.reg_level || undefined,
        reg_authority: savedPrefs.reg_authority || undefined,
        export_content: savedPrefs.export_content || ['enterprise', 'enterprise_standard', 'other_standard', 'tb_association'],
        file_format: savedPrefs.file_format || 'single_excel',
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

      saveExportPreferences({
        agency_type_mode: values.agency_type_mode,
        agency_types: values.agency_types || [],
        export_content: values.export_content,
        file_format: values.file_format,
        reg_level: values.reg_level,
        reg_authority: values.reg_authority,
      });

      const payload: any = {
        export_scope: values.export_scope,
        export_content: values.export_content,
        file_format: values.file_format,
        advanced_filters: {
          agency_type_mode: values.agency_type_mode,
          agency_types: values.agency_types || [],
          reg_level: values.reg_level,
          reg_authority: values.reg_authority,
        },
      };

      if (values.export_scope === 'selected') {
        payload.enterprise_ids = selectedEnterprises.map(c => c.id);
      } else {
        payload.base_filters = {
          ...searchParams,
          q: searchParams.keyword,
          province_id: values.province_id,
          city_id: values.city_id,
          district_id: values.district_id,
          reg_level: values.reg_level,
          reg_authority: values.reg_authority,
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
      <Form form={form} layout="vertical" style={{ marginTop: 12, maxHeight: '70vh', overflowY: 'auto', paddingRight: 6 }}>
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

        {/* 4. 登记所在地 / 登记主管机关筛选 */}
        <Form.Item
          label={
            <Space>
              <Text strong>4. 登记所在地 / 登记主管机关筛选（团体标准与协会）</Text>
              <Tooltip title="针对已发团标协会的法定登记机关(Issu_auth)进行精准筛选。可选择登记层级，或直接输入具体登记民政部门(如闽清县民政局)">
                <InfoCircleOutlined style={{ color: '#1890ff', cursor: 'pointer' }} />
              </Tooltip>
            </Space>
          }
        >
          <Space direction="vertical" style={{ width: '100%' }} size={10}>
            <Space style={{ width: '100%' }} size={8}>
              <Form.Item name="reg_level" noStyle>
                <Select
                  placeholder="登记机关层级(可选)"
                  allowClear
                  style={{ width: 190 }}
                  options={[
                    { label: '全部登记层级', value: '' },
                    { label: '民政部直管 (全国性)', value: 'ministry' },
                    { label: '省民政厅直管 (省级)', value: 'province' },
                    { label: '市民政局直属 (市本级)', value: 'city' },
                    { label: '区县级民政局 (区县级)', value: 'district' },
                  ]}
                />
              </Form.Item>

              <Form.Item name="reg_authority" noStyle>
                <Input
                  prefix={<BankOutlined style={{ color: '#8c8c8c' }} />}
                  placeholder="具体登记机关名称/关键字(如: 闽清县民政局)"
                  allowClear
                  style={{ flex: 1 }}
                />
              </Form.Item>
            </Space>

            {/* 智能快捷带入标签 */}
            {(currentProvinceObj || currentCityObj || currentDistrictObj) && (
              <Space size={6} wrap style={{ alignItems: 'center' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>快捷填入：</Text>
                {currentProvinceObj && (
                  <Tag
                    color="blue"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => {
                      const pName = currentProvinceObj.name.replace(/省|市|自治区|特别行政区/g, '');
                      form.setFieldValue('reg_authority', `${pName}省民政厅`);
                      form.setFieldValue('reg_level', 'province');
                    }}
                  >
                    {currentProvinceObj.name.replace(/省|市|自治区|特别行政区/g, '')}省民政厅
                  </Tag>
                )}
                {currentCityObj && (
                  <Tag
                    color="cyan"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => {
                      form.setFieldValue('reg_authority', `${currentCityObj.name}民政局`);
                      form.setFieldValue('reg_level', 'city');
                    }}
                  >
                    {currentCityObj.name}民政局
                  </Tag>
                )}
                {currentDistrictObj && (
                  <Tag
                    color="green"
                    style={{ cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => {
                      form.setFieldValue('reg_authority', `${currentDistrictObj.name}民政局`);
                      form.setFieldValue('reg_level', 'district');
                    }}
                  >
                    {currentDistrictObj.name}民政局
                  </Tag>
                )}
              </Space>
            )}

            <Text type="secondary" style={{ fontSize: 12 }}>
              说明：支持精确按协会登记民政部门过滤（如福州市民政局、闽清县民政局等）；若上方已选区县，系统会自动优先匹配该区县登记机关。
            </Text>
          </Space>
        </Form.Item>

        <Divider style={{ margin: '12px 0' }} />

        {/* 5. 导出内容选择 (多选) */}
        <Form.Item name="export_content" label={<Text strong>5. 导出内容选择（可多选）</Text>}>
          <Checkbox.Group
            options={[
              { label: '企业目录', value: 'enterprise' },
              { label: '企标目录（自动去重）', value: 'enterprise_standard' },
              { label: '国/行/地/团标目录（自动去重）', value: 'other_standard' },
              { label: '已发布团体标准的协会及团标（基于团标 tb_asso）', value: 'tb_association' },
            ]}
            style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
          />
        </Form.Item>

        <Form.Item name="file_format" label={<Text strong>6. 文件输出方式</Text>}>
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

