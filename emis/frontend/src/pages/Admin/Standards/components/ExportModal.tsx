import React, { useState } from 'react';
import {
  Modal,
  Radio,
  Checkbox,
  Button,
  Space,
  Divider,
  Row,
  Col,
  message,
  Select,
  DatePicker,
  Collapse,
  Tag
} from 'antd';
import {
  FileExcelOutlined,
  FilterOutlined,
  AppstoreOutlined,
  CheckCircleOutlined
} from '@ant-design/icons';
import type { StandardSearchParams } from '@/hooks/useStandardData';
import apiClient from '@/api/client';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;

// 1. 标准属性字段定义
export const STANDARD_FIELDS = [
  { label: '标准编号(原始)', value: 'standard_no' },
  { label: '标准编号(清洗)', value: 'clean_id' },
  { label: '标准名称', value: 'title' },
  { label: '标准类型', value: 'type' },
  { label: '标准状态', value: 'status' },
  { label: '发布日期', value: 'publish_date' },
  { label: '实施日期', value: 'implement_date' },
  { label: '入库时间', value: 'created_at' },
  { label: 'ICS分类号', value: 'ics' },
  { label: 'CCS分类号', value: 'ccs' },
  { label: '解析状态', value: 'is_parsed' },
  { label: '是否挂接PDF', value: 'has_pdf' },
];

// 2. 企业关联属性字段定义
export const COMPANY_FIELDS = [
  { label: '起草单位/企业名称', value: 'company_name' },
  { label: '统一社会信用代码', value: 'credit_code' },
  { label: '法定代表人', value: 'legal_person' },
  { label: '所属省份', value: 'province' },
  { label: '所属城市', value: 'city' },
  { label: '所属区县', value: 'district' },
  { label: '企业详细地址', value: 'company_address' },
  { label: '企业(机构)类型', value: 'company_type' },
  { label: '企业规模', value: 'company_size' },
];

const ALL_FIELDS = [...STANDARD_FIELDS, ...COMPANY_FIELDS];
const ALL_FIELD_KEYS = ALL_FIELDS.map(f => f.value);

// 预设配置模板
const PRESET_TEMPLATES: Record<string, string[]> = {
  common: [
    'standard_no', 'title', 'company_name', 'status',
    'publish_date', 'implement_date', 'province', 'city', 'district', 'has_pdf'
  ],
  all: ALL_FIELD_KEYS,
  compliance: [
    'standard_no', 'title', 'company_name', 'credit_code',
    'legal_person', 'province', 'city', 'district', 'status', 'has_pdf', 'is_parsed'
  ],
  tech: [
    'standard_no', 'title', 'company_name', 'status',
    'publish_date', 'implement_date', 'ics', 'ccs'
  ],
};

interface ExportModalProps {
  open: boolean;
  onCancel: () => void;
  selectedIds: React.Key[];
  currentFilters: StandardSearchParams;
  totalFilteredCount: number;
}

const ExportModal: React.FC<ExportModalProps> = ({
  open,
  onCancel,
  selectedIds,
  currentFilters,
  totalFilteredCount,
}) => {
  const [exportScope, setExportScope] = useState<'selected' | 'query' | 'all'>('query');
  const [selectedFields, setSelectedFields] = useState<string[]>(PRESET_TEMPLATES.common);
  const [exporting, setExporting] = useState(false);

  // 高级补充过滤条件
  const [advStatus, setAdvStatus] = useState<string | undefined>(undefined);
  const [advHasPdf, setAdvHasPdf] = useState<string | undefined>(undefined);
  const [advIsParsed, setAdvIsParsed] = useState<string | undefined>(undefined);
  const [dateType, setDateType] = useState<'publish_date' | 'implement_date'>('publish_date');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  // 初始化范围
  React.useEffect(() => {
    if (open) {
      if (selectedIds.length > 0) {
        setExportScope('selected');
      } else {
        setExportScope('query');
      }
    }
  }, [open, selectedIds.length]);

  // 模板应用
  const handleApplyPreset = (presetKey: string) => {
    const fields = PRESET_TEMPLATES[presetKey];
    if (fields) {
      setSelectedFields(fields);
    }
  };

  // 全选/清空/反选
  const handleSelectAll = () => setSelectedFields(ALL_FIELD_KEYS);
  const handleClearAll = () => setSelectedFields([]);
  const handleInvert = () => {
    setSelectedFields(prev => ALL_FIELD_KEYS.filter(k => !prev.includes(k)));
  };

  // 执行导出
  const handleExecuteExport = async () => {
    if (selectedFields.length === 0) {
      message.warning('请至少选择一个导出字段');
      return;
    }

    try {
      setExporting(true);
      message.loading({ content: '正在生成并打包企业标准 Excel，请稍候...', key: 'std_export', duration: 0 });

      // 合并页面当前条件与弹窗微调条件
      const mergedFilters: any = {
        ...currentFilters,
      };

      if (advStatus) mergedFilters.status = advStatus;
      if (advHasPdf !== undefined) mergedFilters.has_pdf = advHasPdf;
      if (advIsParsed) mergedFilters.is_parsed = advIsParsed;

      if (dateRange && dateRange[0] && dateRange[1]) {
        mergedFilters.date_type = dateType;
        mergedFilters.start_date = dateRange[0].format('YYYY-MM-DD');
        mergedFilters.end_date = dateRange[1].format('YYYY-MM-DD');
      }

      const response = await apiClient.post(
        '/admin/standards/export/',
        {
          export_scope: exportScope,
          ids: exportScope === 'selected' ? selectedIds : [],
          filters: mergedFilters,
          selected_fields: selectedFields,
        },
        {
          responseType: 'blob',
          timeout: 300000, // 5 分钟超时，满足大数据量导出需求
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      const dateStr = dayjs().format('YYYYMMDD_HHmmss');
      link.setAttribute('download', `企业标准目录导出_${dateStr}.xlsx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.success({ content: '企业标准目录导出成功！', key: 'std_export' });
      onCancel();
    } catch (err: any) {
      let errMsg = '导出失败，请重试';
      if (err?.code === 'ECONNABORTED' || err?.message?.includes('timeout')) {
        errMsg = '导出请求响应超时，当前数据量过大，请适当缩小筛选条件后重试';
      } else if (err?.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const json = JSON.parse(text);
          if (json?.error) {
            errMsg = json.error;
          } else if (json?.message) {
            errMsg = json.message;
          }
        } catch (_) {
          if (err.response?.status === 404) {
            errMsg = '后端导出接口未就绪，请确保服务器端执行了 pm2 restart 重启后端服务';
          } else if (err.response?.status === 504) {
            errMsg = '服务器网关超时，数据量过大，请缩小筛选条件后重试';
          } else if (err.response?.status === 500) {
            errMsg = '服务器内部处理异常，请检查后端日志';
          }
        }
      } else if (err?.response?.data?.error) {
        errMsg = err.response.data.error;
      }
      message.error({ content: errMsg, key: 'std_export', duration: 4 });
    } finally {
      setExporting(false);
    }
  };

  return (
    <Modal
      title={
        <Space style={{ fontSize: 16 }}>
          <FileExcelOutlined style={{ color: '#52c41a' }} />
          <span style={{ fontWeight: 600 }}>导出企业标准目录</span>
        </Space>
      }
      open={open}
      onCancel={onCancel}
      onOk={handleExecuteExport}
      confirmLoading={exporting}
      width={780}
      okText="确认导出 Excel"
      cancelText="取消"
      destroyOnClose
    >
      <div style={{ padding: '6px 0' }}>
        {/* 1. 导出范围配置 */}
        <div style={{ marginBottom: 16 }}>
          <span style={{ fontWeight: 600, display: 'block', marginBottom: 10, color: '#262626' }}>
            1. 导出数据范围：
          </span>
          <Radio.Group
            value={exportScope}
            onChange={(e) => setExportScope(e.target.value)}
            style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
          >
            <Radio value="selected" disabled={selectedIds.length === 0}>
              <span>导出当前选中的标准 </span>
              <Tag color={selectedIds.length > 0 ? 'blue' : 'default'}>
                {selectedIds.length} 条已勾选
              </Tag>
              {selectedIds.length === 0 && (
                <span style={{ color: '#bfbfbf', fontSize: 12, marginLeft: 4 }}>
                  (需在列表勾选行方可选用)
                </span>
              )}
            </Radio>
            <Radio value="query">
              <span>导出当前检索条件下的标准 </span>
              <Tag color="green">当前筛选共 {totalFilteredCount} 条</Tag>
              {totalFilteredCount > 100000 && (
                <span style={{ fontSize: 12, color: '#faad14', marginLeft: 4 }}>
                  (单次最多导出前 100,000 条，建议结合上方搜索或状态筛选收窄范围)
                </span>
              )}
              {currentFilters.keyword && (
                <span style={{ fontSize: 12, color: '#8c8c8c', marginLeft: 4 }}>
                  [关键词: "{currentFilters.keyword}"]
                </span>
              )}
            </Radio>
            <Radio value="all">
              <span>全量导出本地库所有企业标准资产 </span>
              <Tag color="purple">全部数据导出</Tag>
              <span style={{ fontSize: 12, color: '#8c8c8c', marginLeft: 4 }}>
                (忽略页面关键词分页限制，导出完整资产底册)
              </span>
            </Radio>
          </Radio.Group>
        </div>

        <Divider style={{ margin: '14px 0' }} />

        {/* 2. 高级条件折叠面板 */}
        <div style={{ marginBottom: 16 }}>
          <Collapse
            ghost
            items={[
              {
                key: 'advanced_filter',
                label: (
                  <Space style={{ color: '#1677ff', fontWeight: 500, fontSize: 13 }}>
                    <FilterOutlined />
                    <span>添加/微调导出筛选条件（可选）</span>
                  </Space>
                ),
                children: (
                  <div style={{ background: '#f8fafc', padding: 12, borderRadius: 8, marginTop: -8 }}>
                    <Row gutter={[16, 12]} align="middle">
                      <Col span={8}>
                        <div style={{ fontSize: 12, color: '#595959', marginBottom: 4 }}>标准状态：</div>
                        <Select
                          placeholder="保持与页面一致"
                          allowClear
                          value={advStatus}
                          onChange={setAdvStatus}
                          style={{ width: '100%' }}
                          size="small"
                        >
                          <Select.Option value="active">正常运行 (现行)</Select.Option>
                          <Select.Option value="deprecated">已废止</Select.Option>
                          <Select.Option value="draft">草案</Select.Option>
                          <Select.Option value="upcoming">即将实施</Select.Option>
                        </Select>
                      </Col>
                      <Col span={8}>
                        <div style={{ fontSize: 12, color: '#595959', marginBottom: 4 }}>PDF挂接状态：</div>
                        <Select
                          placeholder="不限挂接状态"
                          allowClear
                          value={advHasPdf}
                          onChange={setAdvHasPdf}
                          style={{ width: '100%' }}
                          size="small"
                        >
                          <Select.Option value="true">仅导出已挂接 PDF</Select.Option>
                          <Select.Option value="false">仅导出未挂接 PDF</Select.Option>
                        </Select>
                      </Col>
                      <Col span={8}>
                        <div style={{ fontSize: 12, color: '#595959', marginBottom: 4 }}>解析状态：</div>
                        <Select
                          placeholder="不限解析状态"
                          allowClear
                          value={advIsParsed}
                          onChange={setAdvIsParsed}
                          style={{ width: '100%' }}
                          size="small"
                        >
                          <Select.Option value="unparsed">暂未解析</Select.Option>
                          <Select.Option value="references_parsed">已完成引用解析</Select.Option>
                          <Select.Option value="indicators_parsed">已完成指标解析</Select.Option>
                        </Select>
                      </Col>
                      <Col span={24}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                          <Select
                            value={dateType}
                            onChange={(val) => setDateType(val)}
                            size="small"
                            style={{ width: 110 }}
                          >
                            <Select.Option value="publish_date">发布日期范围</Select.Option>
                            <Select.Option value="implement_date">实施日期范围</Select.Option>
                          </Select>
                          <RangePicker
                            size="small"
                            value={dateRange}
                            onChange={(dates) => setDateRange(dates as any)}
                            style={{ flex: 1 }}
                          />
                        </div>
                      </Col>
                    </Row>
                  </div>
                ),
              },
            ]}
          />
        </div>

        <Divider style={{ margin: '14px 0' }} />

        {/* 3. 自定义导出字段属性 */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 600, color: '#262626' }}>
              2. 自定义导出字段属性（已选 {selectedFields.length} 项）：
            </span>
            <Space size="small">
              <Button size="small" type="link" onClick={handleSelectAll}>全选</Button>
              <Button size="small" type="link" onClick={handleClearAll}>清空</Button>
              <Button size="small" type="link" onClick={handleInvert}>反选</Button>
            </Space>
          </div>

          {/* 预设模版快捷按钮 */}
          <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>预设模版：</span>
            <Space size="small" wrap>
              <Button size="small" style={{ borderRadius: 12 }} onClick={() => handleApplyPreset('common')}>
                常用台账清单 (10列)
              </Button>
              <Button size="small" style={{ borderRadius: 12 }} onClick={() => handleApplyPreset('compliance')}>
                合规审查清单 (11列)
              </Button>
              <Button size="small" style={{ borderRadius: 12 }} onClick={() => handleApplyPreset('tech')}>
                技术分类清单 (8列)
              </Button>
              <Button size="small" style={{ borderRadius: 12 }} onClick={() => handleApplyPreset('all')}>
                导出全量字段 (21列)
              </Button>
            </Space>
          </div>

          {/* 字段 Checkbox Group */}
          <Checkbox.Group
            value={selectedFields}
            onChange={(checked) => setSelectedFields(checked as string[])}
            style={{ width: '100%' }}
          >
            {/* 分组 1: 标准核心属性 */}
            <div style={{ background: '#fafafa', padding: '10px 14px', borderRadius: 8, marginBottom: 12, border: '1px solid #f0f0f0' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#1677ff', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <AppstoreOutlined />
                <span>标准核心信息属性</span>
              </div>
              <Row gutter={[12, 10]}>
                {STANDARD_FIELDS.map(f => (
                  <Col span={6} key={f.value}>
                    <Checkbox value={f.value} style={{ fontSize: 13 }}>
                      {f.label}
                    </Checkbox>
                  </Col>
                ))}
              </Row>
            </div>

            {/* 分组 2: 企业关联属性 */}
            <div style={{ background: '#fafafa', padding: '10px 14px', borderRadius: 8, border: '1px solid #f0f0f0' }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: '#52c41a', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircleOutlined />
                <span>起草单位/关联企业属性</span>
              </div>
              <Row gutter={[12, 10]}>
                {COMPANY_FIELDS.map(f => (
                  <Col span={6} key={f.value}>
                    <Checkbox value={f.value} style={{ fontSize: 13 }}>
                      {f.label}
                    </Checkbox>
                  </Col>
                ))}
              </Row>
            </div>
          </Checkbox.Group>
        </div>
      </div>
    </Modal>
  );
};

export default ExportModal;
