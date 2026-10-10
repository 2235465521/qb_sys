import React, { useState, useMemo } from 'react';
import {
  Modal,
  Tabs,
  Input,
  Button,
  Upload,
  Select,
  Table,
  Tag,
  Space,
  Row,
  Col,
  Alert,
  message,
  Typography,
  Steps
} from 'antd';
import {
  InboxOutlined,
  CloudDownloadOutlined,
  FileExcelOutlined,
  ArrowLeftOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const { Text } = Typography;

interface ListMatchDownloadModalProps {
  open: boolean;
  onClose: () => void;
}

interface SniffHeader {
  index: number;
  letter: string;
  label: string;
  display: string;
}

interface SniffResult {
  sheet_names: string[];
  current_sheet: string;
  header_row_index: number;
  headers: SniffHeader[];
  suggested_std_no_col: string;
  suggested_title_col: string;
  total_rows: number;
}

interface MatchDetailItem {
  index: number;
  input_no: string;
  input_title: string;
  status_code: 'std_no_exact' | 'title_fallback' | 'matched_no_file' | 'not_found';
  status_text: string;
  standard_id: number | null;
  matched_no: string;
  matched_title: string;
  company_name: string;
  publish_date: string;
  status_label: string;
  has_pdf: boolean;
}

interface MatchResultData {
  total_input: number;
  matched_count: number;
  available_file_count: number;
  missing_file_count: number;
  not_found_count: number;
  details: MatchDetailItem[];
}

const MAX_LIMIT = 500;

const ListMatchDownloadModal: React.FC<ListMatchDownloadModalProps> = ({ open, onClose }) => {
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<'paste' | 'upload'>('paste');

  // 模式1：文本粘贴状态
  const [pasteText, setPasteText] = useState<string>('');

  // 模式2：Excel 上传状态
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploadedFileRaw, setUploadedFileRaw] = useState<File | null>(null);
  const [isSniffing, setIsSniffing] = useState<boolean>(false);
  const [sniffResult, setSniffResult] = useState<SniffResult | null>(null);
  const [stdNoColIdx, setStdNoColIdx] = useState<number | undefined>(undefined);
  const [titleColIdx, setTitleColIdx] = useState<number | undefined>(undefined);

  // 匹配中与匹配结果
  const [isMatching, setIsMatching] = useState<boolean>(false);
  const [matchResult, setMatchResult] = useState<MatchResultData | null>(null);

  // 打包与导出状态
  const [isPacking, setIsPacking] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  const { dispatchTask } = useTaskContext();

  // 解析粘贴文本行数
  const parsedPasteItems = useMemo(() => {
    if (!pasteText.trim()) return [];
    const lines = pasteText
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(Boolean);

    return lines.slice(0, MAX_LIMIT).map(line => {
      if (line.includes('\t')) {
        const parts = line.split('\t').map(p => p.trim());
        return { raw_no: parts[0] || '', raw_title: parts[1] || '' };
      }
      // 单列输入：如果是标准号特征（包含斜杠或Q），同时填入 raw_no，否则填入 raw_title
      if (line.includes('/') || /^[a-zA-Z]/.test(line)) {
        return { raw_no: line, raw_title: '' };
      }
      return { raw_no: '', raw_title: line };
    });
  }, [pasteText]);

  // 重置表单
  const handleReset = () => {
    setCurrentStep(0);
    setPasteText('');
    setFileList([]);
    setUploadedFileRaw(null);
    setSniffResult(null);
    setStdNoColIdx(undefined);
    setTitleColIdx(undefined);
    setMatchResult(null);
    setIsMatching(false);
    setIsPacking(false);
    setIsExporting(false);
  };

  const handleModalClose = () => {
    handleReset();
    onClose();
  };

  // 处理 Excel 上传并触发后端表头嗅探
  const handleBeforeUpload = async (file: File) => {
    setUploadedFileRaw(file);
    setFileList([file as any]);
    setIsSniffing(true);
    setSniffResult(null);
    setStdNoColIdx(undefined);
    setTitleColIdx(undefined);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const { data } = await apiClient.post<SniffResult>('/client/standards/sniff-excel/', formData);
      setSniffResult(data);

      // 自动预选列索引
      if (data.suggested_std_no_col) {
        const found = data.headers.find(h => h.letter === data.suggested_std_no_col);
        if (found) setStdNoColIdx(found.index);
      }
      if (data.suggested_title_col) {
        const found = data.headers.find(h => h.letter === data.suggested_title_col);
        if (found) setTitleColIdx(found.index);
      }
      message.success(`成功识别表格，包含 ${data.headers.length} 列，约 ${data.total_rows} 行数据`);
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || '识别 Excel 表格结构失败，请确保格式正确';
      message.error(errorMsg);
      setFileList([]);
      setUploadedFileRaw(null);
    } finally {
      setIsSniffing(false);
    }
    return false; // 阻止 antd 自动上传
  };

  // 提交第一阶段预匹配
  const handleStartMatch = async () => {
    setIsMatching(true);
    try {
      if (activeTab === 'paste') {
        if (parsedPasteItems.length === 0) {
          message.warning('请先输入或粘贴待匹配的标准编号或名称');
          setIsMatching(false);
          return;
        }

        const { data } = await apiClient.post<MatchResultData>('/client/standards/list-match-preview/', {
          items: parsedPasteItems
        });
        setMatchResult(data);
        setCurrentStep(1);
        message.success(`匹配完成！共命中 ${data.matched_count} 条，其中 ${data.available_file_count} 份已有归档 PDF`);
      } else {
        // Excel 模式
        if (!uploadedFileRaw) {
          message.warning('请先上传包含标准的 Excel 文件');
          setIsMatching(false);
          return;
        }
        if (stdNoColIdx === undefined && titleColIdx === undefined) {
          message.warning('请至少指定一列为【标准编号】或【标准名称】');
          setIsMatching(false);
          return;
        }

        const formData = new FormData();
        formData.append('file', uploadedFileRaw);
        if (sniffResult?.current_sheet) {
          formData.append('sheet_name', sniffResult.current_sheet);
        }
        if (stdNoColIdx !== undefined) {
          formData.append('std_no_col_idx', String(stdNoColIdx));
        }
        if (titleColIdx !== undefined) {
          formData.append('title_col_idx', String(titleColIdx));
        }
        if (sniffResult?.header_row_index !== undefined) {
          formData.append('header_row_idx', String(sniffResult.header_row_index));
        }

        const { data } = await apiClient.post<MatchResultData>('/client/standards/list-match-preview/', formData);
        setMatchResult(data);
        setCurrentStep(1);
        message.success(`匹配完成！共命中 ${data.matched_count} 条，其中 ${data.available_file_count} 份已有归档 PDF`);
      }
    } catch (err: any) {
      const errorMsg = err.response?.data?.error || '匹配分析请求失败，请检查网络或数据格式';
      message.error(errorMsg);
    } finally {
      setIsMatching(false);
    }
  };

  // 导出对账清单 Excel
  const handleExportManifest = async () => {
    if (!matchResult || !matchResult.details.length) return;
    setIsExporting(true);
    const hide = message.loading('正在导出匹配与对账清单 Excel，请稍候...', 0);
    try {
      const { data: fileBlob } = await apiClient.post(
        '/client/standards/export-match-manifest/',
        { details: matchResult.details },
        { responseType: 'blob' }
      );
      hide();

      const blob = new Blob([fileBlob], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', '企标匹配与下载对账清单.xlsx');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      message.success('对账清单 Excel 导出成功！');
    } catch (err) {
      hide();
      message.error('导出对账清单失败，请稍后重试');
    } finally {
      setIsExporting(false);
    }
  };

  // 提交最终打包下载任务
  const handleConfirmPack = async () => {
    if (!matchResult) return;

    // 收集所有拥有有效 PDF 的 standard_id
    const targetIds = matchResult.details
      .filter(item => item.has_pdf && item.standard_id)
      .map(item => item.standard_id as number);

    if (targetIds.length === 0) {
      message.warning('当前没有可供下载打包的有效 PDF 电子文件');
      return;
    }

    setIsPacking(true);
    const hide = message.loading('正在提交清单打包任务到后台队列...', 0);
    try {
      const payload = {
        standard_ids: targetIds,
        manifest_data: matchResult.details
      };

      const { data } = await apiClient.post<{ token: string; count: number; status: string }>(
        '/client/standards/list-match-pack/',
        payload
      );
      hide();

      const { token, count } = data;
      message.success(`已锁定 ${count} 份企标全文，后台打包任务已开始处理，系统将自动生成审计清单并压缩...`);
      dispatchTask(token, `清单匹配打包 (${count}份)`, false, '/client/standards/list-match-pack/', payload);

      handleModalClose();
    } catch (err: any) {
      hide();
      const errMsg = err.response?.data?.error || '打包任务提交失败，请稍后重试';
      message.error(errMsg);
    } finally {
      setIsPacking(false);
    }
  };

  // 表格列定义
  const columns = [
    {
      title: '序号',
      dataIndex: 'index',
      width: 60,
      align: 'center' as const
    },
    {
      title: '原始输入',
      key: 'raw_input',
      width: 170,
      render: (_: any, r: MatchDetailItem) => (
        <div>
          {r.input_no && <div style={{ fontWeight: 500, color: '#334155' }}>{r.input_no}</div>}
          {r.input_title && <div style={{ fontSize: 12, color: '#64748b' }}>{r.input_title}</div>}
          {!r.input_no && !r.input_title && <span style={{ color: '#94a3b8' }}>-</span>}
        </div>
      )
    },
    {
      title: '匹配结果',
      dataIndex: 'status_code',
      width: 130,
      render: (code: string) => {
        if (code === 'std_no_exact') {
          return <Tag color="green" icon={<CheckCircleOutlined />}>标准号命中</Tag>;
        }
        if (code === 'title_fallback') {
          return <Tag color="cyan" icon={<ThunderboltOutlined />}>名称降级命中</Tag>;
        }
        if (code === 'matched_no_file') {
          return <Tag color="orange" icon={<ExclamationCircleOutlined />}>命中暂无文件</Tag>;
        }
        return <Tag color="red" icon={<CloseCircleOutlined />}>未收录</Tag>;
      }
    },
    {
      title: '命中的标准编号',
      dataIndex: 'matched_no',
      width: 170,
      render: (v: string) => (
        <span style={{ color: v !== '-' ? '#0d9488' : '#94a3b8', fontWeight: 500 }}>
          {v}
        </span>
      )
    },
    {
      title: '命中的标准名称',
      dataIndex: 'matched_title',
      ellipsis: true,
      render: (v: string) => (
        <span style={{ color: v !== '-' ? '#1e293b' : '#94a3b8' }}>{v}</span>
      )
    },
    {
      title: '起草单位',
      dataIndex: 'company_name',
      ellipsis: true,
      width: 180,
      render: (v: string) => (
        <span style={{ color: v !== '-' ? '#475569' : '#94a3b8', fontSize: 13 }}>{v}</span>
      )
    },
    {
      title: 'PDF文件',
      dataIndex: 'has_pdf',
      width: 90,
      align: 'center' as const,
      render: (has: boolean) => (
        has ? (
          <Tag color="success" style={{ margin: 0 }}>有文件</Tag>
        ) : (
          <Tag color="default" style={{ margin: 0, color: '#94a3b8' }}>缺档</Tag>
        )
      )
    }
  ];

  return (
    <Modal
      open={open}
      onCancel={handleModalClose}
      width={920}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16 }}>
          <CloudDownloadOutlined style={{ color: '#00838f', fontSize: 20 }} />
          <span>按外部清单批量匹配与打包下载</span>
        </div>
      }
      footer={null}
      destroyOnClose
      styles={{ body: { paddingTop: 12, paddingBottom: 16 } }}
    >
      <Steps
        current={currentStep}
        size="small"
        style={{ marginBottom: 20, padding: '0 20px' }}
        items={[
          { title: '提供外部清单 (粘贴/Excel)' },
          { title: '匹配核对与确认打包' }
        ]}
      />

      {/* ── 步骤 0：输入阶段 ─────────────────────────────────────────── */}
      {currentStep === 0 && (
        <div>
          <Tabs
            activeKey={activeTab}
            onChange={(k) => setActiveTab(k as any)}
            type="card"
            items={[
              {
                key: 'paste',
                label: '📝 文本批量粘贴',
                children: (
                  <div style={{ padding: '8px 4px' }}>
                    <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        请输入或从 Excel 复制粘贴标准编号或标准名称（一行一条，支持同时复制两列）：
                      </Text>
                      {parsedPasteItems.length > 0 && (
                        <Tag color="cyan">
                          已识别 {parsedPasteItems.length} 行待比对
                        </Tag>
                      )}
                    </div>

                    <Input.TextArea
                      rows={10}
                      value={pasteText}
                      onChange={(e) => setPasteText(e.target.value)}
                      placeholder={`示例 1（纯标准号）：\nQ/ZJHJ001-2021\nQ/ZJLT001-2023\n\n示例 2（从 Excel 复制的两列制表符分隔）：\nQ/ZJHJ001-2021\t挥发性有机化合物 (VOCs) 净化设备\nQ/ZJLT001-2023\t条盒捆扎机使用规范\n\n示例 3（仅有标准名称）：\n超洁净磁悬浮泵\n全包型打包机`}
                      style={{
                        fontFamily: 'Consolas, Monaco, monospace',
                        fontSize: 13,
                        borderRadius: 8,
                        borderColor: '#cbd5e1'
                      }}
                    />

                    <Alert
                      type="info"
                      showIcon
                      icon={<InfoCircleOutlined />}
                      style={{ marginTop: 12, borderRadius: 8, fontSize: 12 }}
                      message={
                        <span>
                          系统将逐行优先比对<b>【标准编号】</b>；若编号未命中或为空，自动降级比对<b>【标准名称】</b>。单次建议不超过 {MAX_LIMIT} 条。
                        </span>
                      }
                    />
                  </div>
                )
              },
              {
                key: 'upload',
                label: '📁 上传 Excel 文件',
                children: (
                  <div style={{ padding: '8px 4px' }}>
                    <Upload.Dragger
                      accept=".xlsx,.xls"
                      fileList={fileList}
                      beforeUpload={handleBeforeUpload}
                      onRemove={() => {
                        setFileList([]);
                        setUploadedFileRaw(null);
                        setSniffResult(null);
                        setStdNoColIdx(undefined);
                        setTitleColIdx(undefined);
                      }}
                      maxCount={1}
                      style={{
                        padding: '24px 0',
                        borderRadius: 12,
                        background: '#f8fafc',
                        border: '2px dashed #94a3b8'
                      }}
                    >
                      <p className="ant-upload-drag-icon">
                        <InboxOutlined style={{ color: '#00838f', fontSize: 44 }} />
                      </p>
                      <p style={{ fontSize: 15, fontWeight: 500, color: '#1e293b', marginBottom: 4 }}>
                        点击或将 Excel 文件拖拽到此处
                      </p>
                      <p style={{ fontSize: 12, color: '#64748b' }}>
                        支持 .xlsx / .xls 文件，大小不超过 10MB。系统将自动扫描表头并建立列映射。
                      </p>
                    </Upload.Dragger>

                    {/* 智能表头识别与映射区域 */}
                    {isSniffing && (
                      <div style={{ marginTop: 16, textAlign: 'center', color: '#00838f', padding: 12 }}>
                        正在智能嗅探 Excel 表头与数据列...
                      </div>
                    )}

                    {sniffResult && (
                      <div
                        style={{
                          marginTop: 16,
                          padding: 16,
                          borderRadius: 8,
                          background: '#f0fdfa',
                          border: '1px solid #ccfbf1'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                          <span style={{ fontWeight: 600, color: '#0f766e', fontSize: 14 }}>
                            ✓ 表头识别完成（工作表: {sniffResult.current_sheet}，数据行: 约 {sniffResult.total_rows} 行）
                          </span>
                        </div>

                        <Row gutter={16}>
                          <Col span={12}>
                            <div style={{ marginBottom: 4, fontSize: 13, color: '#334155', fontWeight: 500 }}>
                              主匹配列（标准编号列）：
                            </div>
                            <Select
                              placeholder="请选择标准编号对应列"
                              value={stdNoColIdx}
                              onChange={(v) => setStdNoColIdx(v)}
                              style={{ width: '100%' }}
                              allowClear
                              options={sniffResult.headers.map(h => ({
                                value: h.index,
                                label: h.index === stdNoColIdx ? `${h.display} (已选)` : h.display
                              }))}
                            />
                          </Col>
                          <Col span={12}>
                            <div style={{ marginBottom: 4, fontSize: 13, color: '#334155', fontWeight: 500 }}>
                              备用降级列（标准名称列）：
                            </div>
                            <Select
                              placeholder="请选择标准名称对应列（可选）"
                              value={titleColIdx}
                              onChange={(v) => setTitleColIdx(v)}
                              style={{ width: '100%' }}
                              allowClear
                              options={sniffResult.headers.map(h => ({
                                value: h.index,
                                label: h.index === titleColIdx ? `${h.display} (已选)` : h.display
                              }))}
                            />
                          </Col>
                        </Row>

                        <div style={{ marginTop: 10, fontSize: 12, color: '#0d9488' }}>
                          💡 匹配规则：逐行优先匹配【标准编号】列；若未找到，自动使用同行的【标准名称】列进行二次降级检索。
                        </div>
                      </div>
                    )}
                  </div>
                )
              }
            ]}
          />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 24 }}>
            <Button onClick={handleModalClose}>取消</Button>
            <Button
              type="primary"
              icon={<ArrowRightOutlined />}
              loading={isMatching}
              disabled={
                activeTab === 'paste'
                  ? parsedPasteItems.length === 0
                  : (!uploadedFileRaw || (stdNoColIdx === undefined && titleColIdx === undefined))
              }
              onClick={handleStartMatch}
              style={{
                borderRadius: 8,
                background: 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
                borderColor: '#00acc1',
                fontWeight: 500
              }}
            >
              开始智能匹配
            </Button>
          </div>
        </div>
      )}

      {/* ── 步骤 1：匹配结果核对与确认打包 ──────────────────────────── */}
      {currentStep === 1 && matchResult && (
        <div>
          {/* 指标卡片面板 */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
            <div style={{ padding: '12px 16px', background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
              <div style={{ fontSize: 12, color: '#64748b' }}>待匹配总数</div>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: '#1e293b' }}>{matchResult.total_input}</div>
            </div>
            <div style={{ padding: '12px 16px', background: '#f0fdf4', borderRadius: 8, border: '1px solid #bbf7d0' }}>
              <div style={{ fontSize: 12, color: '#166534' }}>成功匹配条数</div>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: '#15803d' }}>{matchResult.matched_count}</div>
            </div>
            <div style={{ padding: '12px 16px', background: '#f0fdfa', borderRadius: 8, border: '1px solid #99f6e4' }}>
              <div style={{ fontSize: 12, color: '#0f766e' }}>可下载 PDF 全文</div>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: '#0d9488' }}>{matchResult.available_file_count}</div>
            </div>
            <div style={{ padding: '12px 16px', background: '#fffbeb', borderRadius: 8, border: '1px solid #fde68a' }}>
              <div style={{ fontSize: 12, color: '#92400e' }}>缺档 / 未收录</div>
              <div style={{ fontSize: 20, fontWeight: 'bold', color: '#b45309' }}>
                {matchResult.missing_file_count + matchResult.not_found_count}
              </div>
            </div>
          </div>

          {/* 表格操作栏 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: 13, color: '#475569', fontWeight: 500 }}>
              匹配结果明细表（共 {matchResult.details.length} 行）：
            </span>
            <Button
              size="small"
              icon={<FileExcelOutlined style={{ color: '#16a34a' }} />}
              onClick={handleExportManifest}
              loading={isExporting}
              style={{ borderRadius: 6 }}
            >
              导出匹配明细表 (.xlsx)
            </Button>
          </div>

          {/* 明细表格 */}
          <Table
            columns={columns}
            dataSource={matchResult.details}
            rowKey="index"
            size="small"
            pagination={{ pageSize: 6, showTotal: (total) => `共 ${total} 条` }}
            scroll={{ y: 260 }}
            style={{ borderRadius: 8, border: '1px solid #f1f5f9' }}
          />

          <div style={{ marginTop: 12, fontSize: 12, color: '#64748b' }}>
            💡 提示：点击“确认打包下载”后，系统将在后台自动将所有有效 PDF 按照 <b>[标准编号] 标准名称.pdf</b> 格式规范重命名并压入 ZIP，同时在压缩包内附带一份完整的对账明细清单。
          </div>

          {/* 底部按钮 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20 }}>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => setCurrentStep(0)}
            >
              上一步 / 重新输入
            </Button>

            <Space>
              <Button onClick={handleModalClose}>关闭</Button>
              <Button
                type="primary"
                icon={<CloudDownloadOutlined />}
                loading={isPacking}
                disabled={matchResult.available_file_count === 0}
                onClick={handleConfirmPack}
                style={{
                  borderRadius: 8,
                  background: matchResult.available_file_count === 0
                    ? undefined
                    : 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
                  borderColor: '#00acc1',
                  fontWeight: 'bold',
                  boxShadow: '0 4px 12px rgba(0, 131, 143, 0.25)'
                }}
              >
                确认打包下载 ({matchResult.available_file_count} 份有效文件)
              </Button>
            </Space>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default ListMatchDownloadModal;
