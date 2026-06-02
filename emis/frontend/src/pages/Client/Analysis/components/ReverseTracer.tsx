import React, { useState, useEffect } from 'react';
import { Card, Input, Button, Tag, Space, Typography, Alert, Divider, Drawer, Form, Select, Table, Pagination, Tooltip, message } from 'antd';
import { SearchOutlined, BankOutlined, EnvironmentOutlined, UserOutlined, CheckCircleOutlined, InfoCircleOutlined, CustomerServiceOutlined, PhoneOutlined, WechatOutlined, ArrowLeftOutlined, EyeOutlined } from '@ant-design/icons';
import { useCompanyLeads } from '@/hooks/useCompanyLeads';
import type { Standard, PaginatedResponse } from '@/types';
import apiClient from '@/api/client';

const { Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;

const ReverseTracer: React.FC = () => {
  const [keyword, setKeyword] = useState('');
  const [searchParams, setSearchParams] = useState({ page: 1, keyword: '' });
  const [selectedStandard, setSelectedStandard] = useState<Standard | null>(null);
  
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form] = Form.useForm();

  // 本地管理数据加载状态和数据池，并在 finally 块中释放 loading，防止首次进入 Infinite Loading 转圈圈
  const [standards, setStandards] = useState<Standard[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const { createLeadMutation } = useCompanyLeads();

  const fetchStandards = async () => {
    setLoading(true);
    try {
      const { data } = await apiClient.get<PaginatedResponse<Standard>>('/client/standards/', {
        params: {
          page: searchParams.page,
          keyword: searchParams.keyword,
          type: 'enterprise',
        }
      });
      setStandards(data.results || []);
      setTotalCount(data.count || 0);
    } catch (err: any) {
      console.error(err);
      message.error('获取企标反向溯源列表数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStandards();
  }, [searchParams]);

  const handleSearch = (value: string) => {
    setSearchParams({ page: 1, keyword: value.trim() });
    setSelectedStandard(null); // 搜索时回到列表模式
  };

  const handlePageChange = (newPage: number) => {
    setSearchParams({ ...searchParams, page: newPage });
  };

  const handleOpenDrawer = () => {
    if (!selectedStandard || !selectedStandard.company_detail) return;
    
    form.setFieldsValue({
      company: selectedStandard.company_detail.id,
      source: 'active_inquiry',
      status: 'pending',
      contact_name: selectedStandard.company_detail.legal_person || '',
      contact_phone: '',
      contact_wechat: '',
      memo: `【公众号/视频号来访质询】客户因查询企业标准《${selectedStandard.title || ''}》（企标号：${selectedStandard.standard_no}）前来跟进。需提供专业的规范性引用链体检诊断及标准大数据增值会员报告。`,
    });
    setDrawerOpen(true);
  };

  const handleSaveLead = async (values: any) => {
    try {
      await createLeadMutation.mutateAsync(values);
      setDrawerOpen(false);
      form.resetFields();
    } catch (err) {
      // 错误已自动在 mutation onError 呈现
    }
  };

  const columns = [
    {
      title: '标准编号',
      dataIndex: 'standard_no',
      key: 'standard_no',
      render: (text: string) => (
        <span style={{ fontWeight: 'bold', color: '#13c2c2', fontFamily: 'Courier New, monospace' }}>
          {text}
        </span>
      ),
    },
    {
      title: '标准名称',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '起草单位',
      dataIndex: ['company_detail', 'name'],
      key: 'company_name',
      ellipsis: true,
      render: (text: string) => text ? (
        <Tooltip title={text} placement="topLeft">
          <Tag 
            color="cyan" 
            style={{ 
              borderRadius: 4, 
              maxWidth: '100%', 
              overflow: 'hidden', 
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              display: 'inline-block',
              verticalAlign: 'middle'
            }}
          >
            {text}
          </Tag>
        </Tooltip>
      ) : '--',
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: Standard) => (
        <Tooltip title="查看详情">
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => setSelectedStandard(record)}
            style={{ color: '#0097a7' }}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <SearchOutlined style={{ color: '#13c2c2', fontSize: 18 }} />
          <span style={{ fontWeight: 'bold' }}>企标反向溯源</span>
        </Space>
      }
      bordered={false}
      style={{
        borderRadius: 16,
        boxShadow: '0 6px 20px rgba(0,0,0,0.04)',
        border: '1px solid #f0f0f0',
        background: '#fff',
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
      bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column' }}
    >
      <Paragraph style={{ color: '#666', fontSize: 13, marginBottom: 16 }}>
        支持录入企业标准号（如 Q/XMBL）或企标名称，系统将智能提取其背后的起草企业，精准回显企业画像与打标状态，助您在第一时间提供高质量增值服务。
      </Paragraph>

      {/* 搜索控制栏 (使用 Input.Search 修复搜索过滤失效) */}
      <div style={{ marginBottom: 20 }}>
        <Input.Search
          placeholder="请输入企标编号 / 企标名称模糊检索..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onSearch={handleSearch}
          enterButton="搜索过滤"
          allowClear
          size="large"
          style={{ borderRadius: 8 }}
        />
      </div>

      <Divider style={{ margin: '16px 0' }} />

      {selectedStandard ? (
        /* 单个标准的定位画像详情模式 */
        <div className="trace-result-container">
          <Button
            type="link"
            icon={<ArrowLeftOutlined />}
            onClick={() => setSelectedStandard(null)}
            style={{ paddingLeft: 0, marginBottom: 16, color: '#0097a7' }}
          >
            返回企标列表
          </Button>

          {/* 企标元信息 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 12 }}>标准编号</Text>
              <div style={{ fontWeight: 'bold', fontSize: 18, color: '#13c2c2', fontFamily: 'Courier New, monospace', marginTop: 2 }}>
                {selectedStandard.standard_no}
              </div>
            </div>
            <div>
              {selectedStandard.is_parsed === 'indicators_parsed' ? (
                <Tag color="purple" style={{ borderRadius: 6, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <CheckCircleOutlined /> 已完成指标解析
                </Tag>
              ) : selectedStandard.is_parsed === 'references_parsed' ? (
                <Tag color="blue" style={{ borderRadius: 6, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <CheckCircleOutlined /> 已解析 {selectedStandard.normative_references?.length || 0} 条引用
                </Tag>
              ) : (
                <Tag color="default" style={{ borderRadius: 6, padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <InfoCircleOutlined /> 暂未解析引用
                </Tag>
              )}
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>标准名称</Text>
            <div style={{ fontWeight: 600, fontSize: 15, color: '#262626', marginTop: 2 }}>
              {selectedStandard.title || '--'}
            </div>
          </div>

          {/* 级联企业画像 */}
          {selectedStandard.company_detail ? (
            <Card 
              style={{ 
                background: 'linear-gradient(135deg, #f7fcfc 0%, #eefbfb 100%)', 
                borderRadius: 12, 
                border: '1px solid #d3f2f1' 
              }}
              bodyStyle={{ padding: 16 }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <BankOutlined style={{ fontSize: 18, color: '#0097a7' }} />
                <span style={{ fontWeight: 'bold', fontSize: 16, color: '#006064' }}>
                  {selectedStandard.company_detail.name}
                </span>
                <Tag color={selectedStandard.company_detail.status === 'active' ? 'blue' : 'default'} style={{ borderRadius: 4, marginLeft: 'auto' }}>
                  {selectedStandard.company_detail.status === 'active' ? '正常运行' : '停业/异常'}
                </Tag>
              </div>

              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>统一社会信用代码：</Text>
                  <Text style={{ fontFamily: 'monospace', fontSize: 13, color: '#434343' }}>
                    {selectedStandard.company_detail.credit_code}
                  </Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>法定代表人：</Text>
                  <Text style={{ fontSize: 13, color: '#434343' }}>
                    <UserOutlined /> {selectedStandard.company_detail.legal_person || '--'}
                  </Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>企业所属地区：</Text>
                  <Text style={{ fontSize: 13, color: '#434343' }}>
                    <EnvironmentOutlined /> {selectedStandard.company_detail.province_name} {selectedStandard.company_detail.city_name} {selectedStandard.company_detail.district_name || ''}
                  </Text>
                </div>
              </Space>

              <Divider style={{ margin: '12px 0', borderColor: '#d3f2f1' }} />
              
              <Button 
                type="primary"
                icon={<CustomerServiceOutlined />}
                block
                style={{
                  borderRadius: 6,
                  background: '#00bcd4',
                  borderColor: '#00bcd4',
                  height: 38,
                  fontWeight: 'bold'
                }}
                onClick={handleOpenDrawer}
              >
                第一时间提供企业定制服务
              </Button>
            </Card>
          ) : (
            <Alert
              message="暂无关联企业数据"
              description="数据库中该企标暂未关联任何起草企业，您可以联系管理员在后台重新导入该企业。"
              type="warning"
              showIcon
            />
          )}
        </div>
      ) : (
        /* 列表表格模式 */
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <Table
            columns={columns}
            dataSource={standards}
            rowKey="id"
            loading={loading}
            pagination={false}
            bordered
            size="small"
            style={{ borderRadius: 8, overflow: 'hidden' }}
          />

          {totalCount > 0 && (
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>共计 {totalCount} 条企标归属记录</Text>
              <Pagination
                current={searchParams.page}
                pageSize={10}
                total={totalCount}
                onChange={handlePageChange}
                showSizeChanger={false}
                showQuickJumper
                simple
              />
            </div>
          )}
        </div>
      )}

      {/* B2B 意向客户 CRM 快捷建档 Drawer */}
      <Drawer
        title={
          <Space>
            <CustomerServiceOutlined style={{ color: '#00bcd4' }} />
            <span>B2B 意向销售线索建档</span>
          </Space>
        }
        placement="right"
        width={480}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        bodyStyle={{ paddingBottom: 80 }}
      >
        {selectedStandard && selectedStandard.company_detail && (
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSaveLead}
            requiredMark
          >
            <div style={{ padding: 16, background: '#f5f7fa', borderRadius: 8, marginBottom: 24, borderLeft: '4px solid #00bcd4' }}>
              <div style={{ fontWeight: 'bold', color: '#333', marginBottom: 8 }}>
                <BankOutlined /> 锁定归属企业
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#006064', marginBottom: 4 }}>
                {selectedStandard.company_detail.name}
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>
                统一社会信用代码：{selectedStandard.company_detail.credit_code}
              </div>
            </div>

            <Form.Item name="company" hidden>
              <Input />
            </Form.Item>

            <Form.Item
              name="source"
              label="意向来访渠道"
              rules={[{ required: true, message: '请选择销售线索来源渠道' }]}
            >
              <Select placeholder="请选择渠道来源">
                <Option value="active_inquiry">主动咨询</Option>
                <Option value="wechat_mp">微信公众号咨询</Option>
                <Option value="wechat_video">视频号互动留言</Option>
                <Option value="referral">客户/朋友转介绍</Option>
                <Option value="other">其他渠道</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="contact_name"
              label="联系人姓名"
              rules={[{ required: true, message: '请输入企业联系人姓名' }]}
            >
              <Input prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} placeholder="如：李经理 / 张总" />
            </Form.Item>

            <Form.Item
              name="contact_phone"
              label="联系电话"
              rules={[{ required: true, message: '请输入意向联系电话' }]}
            >
              <Input prefix={<PhoneOutlined style={{ color: '#bfbfbf' }} />} placeholder="用于跟进的手机或座机号码" />
            </Form.Item>

            <Form.Item
              name="contact_wechat"
              label="微信号"
            >
              <Input prefix={<WechatOutlined style={{ color: '#bfbfbf' }} />} placeholder="用于添加微信好友跟进的微信号" />
            </Form.Item>

            <Form.Item
              name="status"
              label="当前跟进状态"
              rules={[{ required: true, message: '请选择当前跟进进度' }]}
            >
              <Select placeholder="请选择跟进进度">
                <Option value="pending">待联系</Option>
                <Option value="contacted">已沟通</Option>
                <Option value="interested">意向会员</Option>
                <Option value="won">成功签约</Option>
                <Option value="lost">跟进流失</Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="memo"
              label="沟通跟进备注记录"
              rules={[{ required: true, message: '请输入首期沟通记录' }]}
            >
              <TextArea rows={5} placeholder="记录此次跟进的详细沟通要点与增值会员跟进诉求..." style={{ borderRadius: 6 }} />
            </Form.Item>

            <div style={{ position: 'absolute', right: 0, bottom: 0, width: '100%', borderTop: '1px solid #e9e9e9', padding: '10px 16px', background: '#fff', textAlign: 'right', zIndex: 1 }}>
              <Space>
                <Button onClick={() => setDrawerOpen(false)} style={{ borderRadius: 6 }}>取消</Button>
                <Button type="primary" htmlType="submit" loading={createLeadMutation.isPending} style={{ borderRadius: 6, background: '#00bcd4', borderColor: '#00bcd4' }}>提交建档</Button>
              </Space>
            </div>
          </Form>
        )}
      </Drawer>
    </Card>
  );
};

export default ReverseTracer;
