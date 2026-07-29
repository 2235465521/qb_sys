import React, { useState } from 'react';
import {
  Table,
  Card,
  Button,
  Space,
  Modal,
  Form,
  Select,
  Radio,
  DatePicker,
  Input,
  Tag,
  Progress,
  Statistic,
  Row,
  Col,
  Typography,
} from 'antd';
import {
  PlusOutlined,
  SendOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { useSmsTaskData } from '@/hooks/useSmsTaskData';
import type { SmsTask } from '@/types';
import dayjs from 'dayjs';
import ErrorBoundary from '@/components/ErrorBoundary';

const { Text } = Typography;

const SmsTasksPage: React.FC = () => {
  const [params, setParams] = useState<{ page: number }>({ page: 1 });
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  
  // 监听发送群体与发送类型的选择，用于条件渲染
  const targetGroup = Form.useWatch('target_group', form);
  const scheduledType = Form.useWatch('scheduled_type', form);

  const { taskQuery, activeTemplatesQuery, createTaskMutation } = useSmsTaskData(params);

  const handleCreateTask = () => {
    form.resetFields();
    setModalVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      
      const payload = {
        template: values.template,
        target_group: values.target_group,
        target_company: values.target_company,
        scheduled_time: values.scheduled_type === 'scheduled' && values.scheduled_time 
          ? values.scheduled_time.toISOString() 
          : null,
      };

      createTaskMutation.mutate(payload, {
        onSuccess: () => {
          setModalVisible(false);
          form.resetFields();
        },
      });
    } catch {
      // 校验未通过
    }
  };

  // 计算简易统计数据，防空容错
  const taskList = taskQuery.data?.results || [];
  const totalTasks = taskQuery.data?.count || 0;
  const totalSentCount = taskList.reduce((acc, t) => acc + (t.sent_count || 0), 0);
  const totalFailedCount = taskList.reduce((acc, t) => acc + (t.failed_count || 0), 0);

  // 渲染发送状态 Tag
  const renderStatusTag = (status: string, display: string) => {
    switch (status) {
      case 'pending':
        return <Tag icon={<ClockCircleOutlined />} color="default">{display}</Tag>;
      case 'running':
        return <Tag icon={<SyncOutlined spin />} color="processing">{display}</Tag>;
      case 'done':
        return <Tag icon={<CheckCircleOutlined />} color="success">{display}</Tag>;
      case 'failed':
        return <Tag icon={<CloseCircleOutlined />} color="error">{display}</Tag>;
      case 'partial':
        return <Tag icon={<ExclamationCircleOutlined />} color="warning">{display}</Tag>;
      default:
        return <Tag>{display}</Tag>;
    }
  };

  const columns = [
    {
      title: '任务ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '所用模板',
      dataIndex: 'template_name',
      key: 'template_name',
      width: 160,
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '目标群体',
      dataIndex: 'target_group',
      key: 'target_group',
      width: 150,
      render: (group: string, record: SmsTask) => {
        if (group === 'all_active') {
          return <Tag color="blue">全部活跃会员</Tag>;
        }
        if (group === 'specific_company') {
          return (
            <Space direction="vertical" size={0}>
              <Tag color="purple">指定单位会员</Tag>
              {record.target_company && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  单位包含: {record.target_company}
                </Text>
              )}
            </Space>
          );
        }
        return <Tag>{group}</Tag>;
      },
    },
    {
      title: '发送进度 / 成功率',
      key: 'progress',
      width: 180,
      render: (_: unknown, record: SmsTask) => {
        const total = record.total_count || 0;
        const sent = record.sent_count || 0;
        const failed = record.failed_count || 0;
        
        if (record.status === 'pending') {
          return <Text type="secondary">等待执行...</Text>;
        }
        
        const percent = total > 0 ? Math.round((sent / total) * 100) : 0;
        return (
          <div style={{ width: '100%' }}>
            <Progress 
              percent={percent} 
              size="small" 
              status={record.status === 'failed' ? 'exception' : percent === 100 ? 'success' : 'active'}
              style={{ marginBottom: 0 }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 4 }}>
              <Text type="secondary">总数: {total}</Text>
              <Text type="success">成功: {sent}</Text>
              {failed > 0 && <Text type="danger">失败: {failed}</Text>}
            </div>
          </div>
        );
      },
    },
    {
      title: '发送状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string, record: SmsTask) => renderStatusTag(status, record.status_display),
    },
    {
      title: '发送计划 / 时间',
      key: 'time',
      width: 260,
      render: (_: unknown, record: SmsTask) => {
        const scheduled = record.scheduled_time;
        const started = record.started_at;
        const finished = record.finished_at;

        return (
          <Space direction="vertical" size={2}>
            {scheduled ? (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>计划: </Text>
                <Text style={{ fontSize: 12 }}>{dayjs(scheduled).format('YYYY-MM-DD HH:mm')}</Text>
              </div>
            ) : (
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>计划: </Text>
                <Tag color="orange" style={{ margin: 0 }}>即时发送</Tag>
              </div>
            )}
            {started && (
              <div style={{ fontSize: 12, color: '#8c8c8c' }}>
                执行: {dayjs(started).format('MM-dd HH:mm')} → {finished ? dayjs(finished).format('HH:mm') : '执行中'}
              </div>
            )}
          </Space>
        );
      },
    },
    {
      title: '操作人',
      dataIndex: 'created_by',
      key: 'created_by',
      width: 110,
      render: (val: string) => val || <Text type="secondary">系统自动</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <div style={{ padding: '4px' }}>
      {/* 标题 Banner */}
      <div
        style={{
          marginBottom: 20,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 2px 10px rgba(0,0,0,0.02)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#0b1d33', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <SendOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#1a1a1a', fontWeight: 'bold' }}>短信群发任务控制台</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#666' }}>在这里，您可以向会员发起模板短信群发任务，支持即时批量发送和未来的节日定时发送。</p>
          </div>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreateTask}
          style={{ borderRadius: 6, fontWeight: 500, background: '#0b1d33', borderColor: '#0b1d33' }}
        >
          新建群发任务
        </Button>
      </div>

      {/* 简易统计面板 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card bordered={false} style={{ borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.01)' }}>
            <Statistic title="累计群发任务" value={totalTasks} suffix="个" />
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false} style={{ borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.01)' }}>
            <Statistic title="发送目标总人次" value={totalSentCount + totalFailedCount} valueStyle={{ color: '#1890ff' }} suffix="人次" />
          </Card>
        </Col>
        <Col span={8}>
          <Card bordered={false} style={{ borderRadius: 8, boxShadow: '0 2px 8px rgba(0,0,0,0.01)' }}>
            <Statistic title="成功发送" value={totalSentCount} valueStyle={{ color: '#52c41a' }} suffix="条" />
          </Card>
        </Col>
      </Row>

      {/* 任务历史列表表格 */}
      <Card
        title="发送任务历史记录"
        bordered={false}
        style={{ borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }}
      >
        <Table
          dataSource={taskQuery.data?.results}
          columns={columns}
          rowKey="id"
          loading={taskQuery.isLoading}
          pagination={{
            current: params.page,
            pageSize: 10,
            total: taskQuery.data?.count,
            onChange: (page) => setParams({ page }),
            showTotal: (total) => `共计 ${total} 个群发任务记录`,
            showSizeChanger: false,
          }}
          bordered
        />
      </Card>

      {/* 新建群发任务 Modal */}
      <Modal
        title={
          <Space>
            <SendOutlined style={{ color: '#0b1d33' }} />
            <span style={{ fontWeight: 'bold' }}>新建短信群发任务</span>
          </Space>
        }
        open={modalVisible}
        onOk={handleOk}
        onCancel={() => setModalVisible(false)}
        confirmLoading={createTaskMutation.isPending}
        destroyOnClose
        width={550}
        okButtonProps={{ style: { background: '#0b1d33', borderColor: '#0b1d33' } }}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            target_group: 'all_active',
            scheduled_type: 'immediate',
          }}
          style={{ marginTop: 16 }}
        >
          {/* 选择模板 */}
          <Form.Item
            name="template"
            label="选择短信模板"
            rules={[{ required: true, message: '请选择发送模板' }]}
            extra={
              <Text type="secondary" style={{ fontSize: 12 }}>
                仅显示已通过审核并启用的模板。如需新模板，请前往“短信模板管理”添加。
              </Text>
            }
          >
            <Select placeholder="请选择要发送的短信模板">
              {activeTemplatesQuery.data?.map((tmpl) => (
                <Select.Option key={tmpl.id} value={tmpl.id}>
                  {tmpl.name} (内容: {tmpl.content.length > 25 ? `${tmpl.content.substring(0, 25)}...` : tmpl.content})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          {/* 目标群体 */}
          <Form.Item
            name="target_group"
            label="发送目标群体"
            rules={[{ required: true }]}
          >
            <Radio.Group>
              <Radio.Button value="all_active">全部活跃会员</Radio.Button>
              <Radio.Button value="specific_company">指定单位会员</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {/* 关联输入框：指定单位 */}
          {targetGroup === 'specific_company' && (
            <Form.Item
              name="target_company"
              label="指定单位名称关键字"
              rules={[{ required: true, message: '请输入要发送的单位名称或关键字' }]}
            >
              <Input placeholder="输入单位名称或包含的关键字，如: 阿里巴巴" />
            </Form.Item>
          )}

          {/* 发送时间类型 */}
          <Form.Item
            name="scheduled_type"
            label="发送执行时机"
            rules={[{ required: true }]}
          >
            <Radio.Group>
              <Radio.Button value="immediate">立即执行发送</Radio.Button>
              <Radio.Button value="scheduled">预约定时发送</Radio.Button>
            </Radio.Group>
          </Form.Item>

          {/* 关联选择器：定时发送时间 */}
          {scheduledType === 'scheduled' && (
            <Form.Item
              name="scheduled_time"
              label="计划发送执行时间"
              rules={[
                { required: true, message: '请选择计划执行时间' },
                {
                  validator: (_, value) => {
                    if (!value || value.isAfter(dayjs())) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('定时时间必须在当前时间之后'));
                  },
                },
              ]}
            >
              <DatePicker
                showTime
                format="YYYY-MM-DD HH:mm:ss"
                style={{ width: '100%' }}
                placeholder="请选择未来的发送时间"
                disabledDate={(current) => current && current.isBefore(dayjs().startOf('day'))}
              />
            </Form.Item>
          )}

          <div style={{ marginTop: 12, padding: '12px', background: '#f5f5f5', borderRadius: 8, border: '1px solid #e8e8e8' }}>
            <Space align="start">
              <InfoCircleOutlined style={{ color: '#1890ff', marginTop: 3 }} />
              <div style={{ fontSize: 12, color: '#595959' }}>
                提示：短信群发底层任务是由 Celery 队列在后台异步执行的。定时发送会在您指定的计划时间准点通过调度器排队触发发送。
              </div>
            </Space>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default function SmsTasksPageWithErrorBoundary() {
  return (
    <ErrorBoundary>
      <SmsTasksPage />
    </ErrorBoundary>
  );
}
