import React, { useState } from 'react';
import { Card, Table, Tag, Input, Select, Button, Space, Modal, Form, Tooltip, Popconfirm } from 'antd';
import { SearchOutlined, UserOutlined, PhoneOutlined, WechatOutlined, MessageOutlined, CalendarOutlined, EditOutlined, DeleteOutlined, BankOutlined, CustomerServiceOutlined, FilterOutlined } from '@ant-design/icons';
import { useCompanyLeads } from '@/hooks/useCompanyLeads';
import type { CompanyLead } from '@/hooks/useCompanyLeads';

const { Option } = Select;
const { TextArea } = Input;

const AdminLeadsPage: React.FC = () => {
  const [params, setParams] = useState({ page: 1, keyword: '', status: '', source: '' });
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<CompanyLead | null>(null);
  const [form] = Form.useForm();

  const { useAdminLeads, updateLeadMutation, deleteLeadMutation } = useCompanyLeads();
  const { data, isLoading } = useAdminLeads(params);

  const handleSearch = (value: string) => {
    setParams({ ...params, page: 1, keyword: value.trim() });
  };

  const handleFilterChange = (field: 'status' | 'source', value: string) => {
    setParams({ ...params, page: 1, [field]: value });
  };

  const handleOpenEdit = (lead: CompanyLead) => {
    setSelectedLead(lead);
    form.setFieldsValue({
      status: lead.status,
      contact_name: lead.contact_name,
      contact_phone: lead.contact_phone,
      contact_wechat: lead.contact_wechat,
      source: lead.source,
      memo: lead.memo,
    });
    setEditModalOpen(true);
  };

  const handleSaveEdit = async (values: any) => {
    if (!selectedLead || !selectedLead.id) return;
    try {
      await updateLeadMutation.mutateAsync({
        id: selectedLead.id,
        company: selectedLead.company,
        ...values
      });
      setEditModalOpen(false);
    } catch (err) {}
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteLeadMutation.mutateAsync(id);
    } catch (err) {}
  };

  const getSourceTag = (source: string, display: string) => {
    switch (source) {
      case 'wechat_mp':
        return <Tag color="green" style={{ borderRadius: 4 }}>公众号：{display}</Tag>;
      case 'wechat_video':
        return <Tag color="gold" style={{ borderRadius: 4 }}>视频号：{display}</Tag>;
      case 'referral':
        return <Tag color="purple" style={{ borderRadius: 4 }}>{display}</Tag>;
      case 'active_inquiry':
        return <Tag color="cyan" style={{ borderRadius: 4 }}>{display}</Tag>;
      default:
        return <Tag color="default" style={{ borderRadius: 4 }}>{display}</Tag>;
    }
  };

  const getStatusTag = (status: string, display: string) => {
    switch (status) {
      case 'pending':
        return <Tag color="red" style={{ borderRadius: 4 }}>● {display}</Tag>;
      case 'contacted':
        return <Tag color="orange" style={{ borderRadius: 4 }}>● {display}</Tag>;
      case 'interested':
        return <Tag color="blue" style={{ borderRadius: 4 }}>● {display}</Tag>;
      case 'vip_signed':
        return <Tag color="success" style={{ borderRadius: 4 }}>● {display}</Tag>;
      case 'failed':
        return <Tag color="default" style={{ borderRadius: 4 }}>● {display}</Tag>;
      default:
        return <Tag color="default" style={{ borderRadius: 4 }}>● {display}</Tag>;
    }
  };

  const columns = [
    {
      title: '意向企业画像',
      key: 'company',
      render: (record: CompanyLead) => (
        <Space direction="vertical" size={2}>
          <div style={{ fontWeight: 'bold', fontSize: 14, color: '#1677ff' }}>
            <BankOutlined /> {record.company_name}
          </div>
          <div style={{ fontSize: 12, color: '#999', fontFamily: 'monospace' }}>
            信用代码: {record.company_credit_code}
          </div>
        </Space>
      ),
    },
    {
      title: '渠道来源',
      dataIndex: 'source',
      key: 'source',
      width: 140,
      render: (source: string, record: CompanyLead) => getSourceTag(source, record.source_display || source),
    },
    {
      title: '联系人信息',
      key: 'contact',
      width: 200,
      render: (record: CompanyLead) => (
        <Space direction="vertical" size={4} style={{ fontSize: 13 }}>
          <div><UserOutlined style={{ color: '#8c8c8c' }} /> <span style={{ fontWeight: 500 }}>{record.contact_name || '--'}</span></div>
          <div><PhoneOutlined style={{ color: '#8c8c8c' }} /> <span>{record.contact_phone || '--'}</span></div>
          {record.contact_wechat && (
            <div><WechatOutlined style={{ color: '#52c41a' }} /> <span style={{ color: '#52c41a', fontFamily: 'monospace' }}>{record.contact_wechat}</span></div>
          )}
        </Space>
      ),
    },
    {
      title: '跟进进度',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string, record: CompanyLead) => getStatusTag(status, record.status_display || status),
    },
    {
      title: '最新沟通备注 (Memo)',
      dataIndex: 'memo',
      key: 'memo',
      ellipsis: true,
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft">
          <span style={{ color: '#595959', fontSize: 13 }}><MessageOutlined /> {text || '--'}</span>
        </Tooltip>
      ),
    },
    {
      title: '建档时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (date: string) => (
        <span style={{ fontSize: 12, color: '#8c8c8c' }}>
          <CalendarOutlined /> {date ? new Date(date).toLocaleString('zh-CN', { hour12: false }) : '--'}
        </span>
      ),
    },
    {
      title: '管理操作',
      key: 'actions',
      width: 150,
      fixed: 'right' as const,
      render: (record: CompanyLead) => (
        <Space size={12}>
          <Button
            type="link"
            icon={<EditOutlined />}
            style={{ padding: 0 }}
            onClick={() => handleOpenEdit(record)}
          >
            跟进更新
          </Button>
          <Popconfirm
            title="您确定要彻底删除此项意向线索记录吗？"
            onConfirm={() => handleDelete(record.id!)}
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
              style={{ padding: 0 }}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className="admin-leads-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
      <div 
        style={{ 
          marginBottom: 20, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #e6f7ff 0%, #bae7ff 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 2px 10px rgba(0,0,0,0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#1890ff', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <CustomerServiceOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#0050b3', fontWeight: 'bold' }}>线索客户管理 (B2B CRM)</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#096dd9' }}>
              统一汇聚与跟进前台“企业标准反向归属溯源”主动前来进行业务质询的企业线索，对潜在转化意向实施全生命周期漏斗管理。
            </p>
          </div>
        </div>
      </div>

      {/* 搜索与过滤工具栏 */}
      <Card bordered={false} style={{ marginBottom: 16, borderRadius: 12, boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }} bodyStyle={{ padding: 16 }}>
        <Space wrap size={16}>
          <Input.Search
            placeholder="搜索企业名称 / 联系人 / 电话 / 微信..."
            allowClear
            onSearch={handleSearch}
            style={{ width: 300 }}
            enterButton={<Button type="primary" icon={<SearchOutlined />}>检索</Button>}
          />
          
          <Space>
            <span><FilterOutlined style={{ color: '#8c8c8c' }} /> 渠道过滤：</span>
            <Select 
              value={params.source} 
              onChange={(val) => handleFilterChange('source', val)} 
              style={{ width: 150 }}
            >
              <Option value="">全部渠道</Option>
              <Option value="active_inquiry">主动咨询</Option>
              <Option value="wechat_mp">微信公众号</Option>
              <Option value="wechat_video">视频号互动</Option>
              <Option value="referral">好友介绍</Option>
              <Option value="other">其他渠道</Option>
            </Select>
          </Space>

          <Space>
            <span><FilterOutlined style={{ color: '#8c8c8c' }} /> 跟进状态：</span>
            <Select 
              value={params.status} 
              onChange={(val) => handleFilterChange('status', val)} 
              style={{ width: 140 }}
            >
              <Option value="">全部状态</Option>
              <Option value="pending">待联系</Option>
              <Option value="contacted">已沟通</Option>
              <Option value="interested">意向会员</Option>
              <Option value="vip_signed">意向签约</Option>
              <Option value="failed">跟进失败</Option>
            </Select>
          </Space>
        </Space>
      </Card>

      {/* 线索列表大表 */}
      <Card bordered={false} style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }} bodyStyle={{ padding: 0 }}>
        <Table
          dataSource={data?.results || []}
          columns={columns}
          rowKey="id"
          loading={isLoading}
          pagination={{ showQuickJumper: true,
            current: params.page,
            pageSize: 10,
            total: data?.count || 0,
            onChange: (page) => setParams({ ...params, page }),
            showSizeChanger: false,
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 跟进状态及沟通备忘录编辑 Modal */}
      <Modal
        title={
          <Space>
            <EditOutlined style={{ color: '#1890ff' }} />
            <span>跟进线索进度及沟通备注更新</span>
          </Space>
        }
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        footer={null}
        width={500}
      >
        {selectedLead && (
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSaveEdit}
            style={{ marginTop: 16 }}
          >
            <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 8, marginBottom: 20 }}>
              <div style={{ fontSize: 14, fontWeight: 'bold', color: '#333' }}>
                {selectedLead.company_name}
              </div>
              <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                来访渠道：{getSourceTag(selectedLead.source, selectedLead.source_display || selectedLead.source)}
              </div>
            </div>

            <Form.Item
              name="status"
              label="修改跟进进度状态"
              rules={[{ required: true, message: '请选择新进度' }]}
            >
              <Select placeholder="请选择跟进状态">
                <Option value="pending">待联系</Option>
                <Option value="contacted">已沟通</Option>
                <Option value="interested">意向会员</Option>
                <Option value="vip_signed">意向签约</Option>
                <Option value="failed">跟进失败</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="contact_name"
              label="联系人姓名"
              rules={[{ required: true, message: '请输入联系人姓名' }]}
            >
              <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} />
            </Form.Item>

            <Form.Item
              name="contact_phone"
              label="联系电话"
              rules={[{ required: true, message: '请输入联系电话' }]}
            >
              <Input prefix={<PhoneOutlined style={{ color: '#bfbfbf' }} />} />
            </Form.Item>

            <Form.Item
              name="contact_wechat"
              label="联系微信号"
            >
              <Input prefix={<WechatOutlined style={{ color: '#bfbfbf' }} />} />
            </Form.Item>

            <Form.Item
              name="memo"
              label="追加最新跟进沟通备忘录"
              rules={[{ required: true, message: '请记录当前沟通备注以便下次联系' }]}
            >
              <TextArea rows={4} placeholder="在这里补充最新的沟通细节或业务定价反馈记录..." />
            </Form.Item>

            <div style={{ textAlign: 'right', borderTop: '1px solid #f0f0f0', paddingTop: 16, marginTop: 24 }}>
              <Button onClick={() => setEditModalOpen(false)} style={{ marginRight: 8 }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={updateLeadMutation.isPending}>
                确认保存更新
              </Button>
            </div>
          </Form>
        )}
      </Modal>
    </div>
  );
};

export default AdminLeadsPage;
