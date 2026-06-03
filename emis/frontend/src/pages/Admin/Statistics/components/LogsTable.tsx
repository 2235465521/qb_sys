import { Table, Card, Form, Input, Select, DatePicker, Row, Col, Button, Tag } from 'antd';
import { SearchOutlined, ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { RangePicker } = DatePicker;

export interface LogEntry {
  id: number;
  user: number | null;
  username: string;
  real_name: string;
  user_role_display: string;
  ip_address: string;
  path: string;
  method: string;
  action: string;
  keyword: string;
  target_id: string;
  status_code: number;
  duration: number;
  is_warning: boolean;
  created_at: string;
}

interface LogsTableProps {
  logs: LogEntry[];
  total: number;
  current: number;
  pageSize: number;
  isLoading: boolean;
  onTableChange: (page: number, size: number) => void;
  onFilterSubmit: (values: any) => void;
  onReset: () => void;
}

const ACTION_OPTIONS = [
  { label: '全部操作', value: '' },
  { label: '用户登录', value: '用户登录' },
  { label: '新用户注册', value: '新用户注册' },
  { label: '前台检索企业', value: '前台检索企业' },
  { label: '前台查询企标列表', value: '前台查询企标列表' },
  { label: '前台预览企标PDF', value: '前台预览企标PDF' },
  { label: '前台下载企标PDF', value: '前台下载企标PDF' },
  { label: '前台导出企业数据', value: '前台导出企业数据' },
  { label: '解析企标规范性引用', value: '解析企标规范性引用' },
  { label: '后台查询企业列表', value: '后台查询企业列表' },
  { label: '后台更新企业', value: '后台更新企业' },
  { label: '后台导入企标规范', value: '后台导入企标规范' },
  { label: '后台删除企标', value: '后台删除企标' },
  { label: '后台查询会员列表', value: '后台查询会员列表' },
  { label: '后台修改会员档案', value: '后台修改会员档案' },
  { label: '查看系统使用记录与统计', value: '查看系统使用记录与统计' },
];

const WARNING_OPTIONS = [
  { label: '全部状态', value: '' },
  { label: '正常记录', value: 'false' },
  { label: '警报记录', value: 'true' },
];

const LogsTable: React.FC<LogsTableProps> = ({
  logs,
  total,
  current,
  pageSize,
  isLoading,
  onTableChange,
  onFilterSubmit,
  onReset
}) => {
  const [form] = Form.useForm(); // Antd 5 form

  const handleFinish = (values: any) => {
    onFilterSubmit(values);
  };

  const handleResetClick = () => {
    form.resetFields();
    onReset();
  };

  const columns: ColumnsType<LogEntry> = [
    {
      title: '操作时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (text) => <span style={{ fontFamily: 'monospace' }}>{text}</span>,
    },
    {
      title: '操作用户',
      dataIndex: 'real_name',
      key: 'user',
      width: 140,
      render: (_, record) => (
        <div>
          <span style={{ fontWeight: 600, color: '#333' }}>{record.real_name}</span>
          <div style={{ fontSize: 11, color: '#999', fontFamily: 'monospace' }}>@{record.username}</div>
        </div>
      ),
    },
    {
      title: '系统角色',
      dataIndex: 'user_role_display',
      key: 'role',
      width: 110,
      render: (text) => {
        let color = 'default';
        if (text.includes('超级')) color = 'red';
        else if (text.includes('管理')) color = 'blue';
        else if (text.includes('操作')) color = 'orange';
        else if (text.includes('客')) color = 'cyan';
        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: '操作类型',
      dataIndex: 'action',
      key: 'action',
      width: 180,
      render: (text) => <span style={{ fontWeight: 500, color: '#096dd9' }}>{text}</span>,
    },
    {
      title: '客户端 IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 130,
      render: (text) => <code style={{ backgroundColor: '#f5f5f5', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>{text}</code>,
    },
    {
      title: '操作详情',
      key: 'details',
      render: (_, record) => {
        const details = [];
        if (record.keyword) {
          details.push(`检索词: "${record.keyword}"`);
        }
        if (record.target_id) {
          details.push(`目标ID: ${record.target_id}`);
        }
        if (details.length === 0) {
          details.push(`路径: ${record.path}`);
        }
        return <span style={{ color: '#666', fontSize: 13 }}>{details.join(' · ')}</span>;
      },
    },
    {
      title: '状态码',
      dataIndex: 'status_code',
      key: 'status_code',
      width: 80,
      align: 'center',
      render: (code) => {
        const color = code >= 200 && code < 300 ? 'green' : code >= 400 ? 'red' : 'orange';
        return <Tag color={color} style={{ fontWeight: 'bold' }}>{code}</Tag>;
      },
    },
    {
      title: '响应耗时',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      align: 'right',
      render: (val) => <span style={{ color: val > 1.0 ? '#ff4d4f' : '#666', fontWeight: val > 1.0 ? 'bold' : 'normal' }}>{val} 秒</span>,
    },
    {
      title: '审计建议',
      dataIndex: 'is_warning',
      key: 'is_warning',
      width: 100,
      align: 'center',
      render: (warn) => {
        return warn ? (
          <Tag color="error" icon={<WarningOutlined />} style={{ animation: 'pulsate 1.5s infinite alternate' }}>
            高频预警
          </Tag>
        ) : (
          <Tag color="success">安全</Tag>
        );
      },
    },
  ];

  return (
    <Card 
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}><SearchOutlined /> 用户使用明细审计日志</span>} 
      style={{ borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.02)', border: '1px solid #f0f0f0' }}
    >
      {/* CSS Animation for warning pulsate */}
      <style>{`
        @keyframes pulsate {
          0% { box-shadow: 0 0 4px #ff4d4f; }
          100% { box-shadow: 0 0 12px #ff4d4f; }
        }
      `}</style>

      {/* Filter Form */}
      <Form
        form={form}
        layout="vertical"
        onFinish={handleFinish}
        style={{ marginBottom: 24, padding: '16px', backgroundColor: '#fafafa', borderRadius: 12, border: '1px solid #f0f0f0' }}
      >
        <Row gutter={[16, 8]}>
          <Col xs={24} sm={12} md={6}>
            <Form.Item name="keyword" label="用户搜索">
              <Input placeholder="输入用户名 / 真实姓名 / IP" prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />} allowClear />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Form.Item name="action" label="操作类型" initialValue="">
              <Select options={ACTION_OPTIONS} showSearch optionFilterProp="label" />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Form.Item name="is_warning" label="安全警报" initialValue="">
              <Select options={WARNING_OPTIONS} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={24} md={6}>
            <Form.Item name="dates" label="操作时间范围">
              <RangePicker style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>
        <Row justify="end" gutter={8} style={{ marginTop: 8 }}>
          <Col>
            <Button onClick={handleResetClick} icon={<ReloadOutlined />}>重置</Button>
          </Col>
          <Col>
            <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>查询</Button>
          </Col>
        </Row>
      </Form>

      {/* Audit Logs Table */}
      <Table
        dataSource={logs}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current,
          pageSize,
          total,
          showSizeChanger: true,
          pageSizeOptions: ['10', '20', '50', '100'],
          showTotal: (total) => `共 ${total} 条日志记录`,
        }}
        onChange={(pagination) => {
          onTableChange(pagination.current || 1, pagination.pageSize || 20);
        }}
        style={{ overflowX: 'auto' }}
      />
    </Card>
  );
};

export default LogsTable;
