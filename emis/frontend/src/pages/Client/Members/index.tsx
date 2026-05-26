import React, { useState } from 'react';
import { Table, Card, Button, Space, Modal, Input, Tag, Typography, Tabs, Checkbox, message } from 'antd';
import { TeamOutlined, DownloadOutlined } from '@ant-design/icons';
import { useMemberData } from '@/hooks/useMemberData';
import apiClient from '@/api/client';

const { Title, Text } = Typography;

const exportFields = [
  { label: '姓名', value: 'name' },
  { label: '联系电话', value: 'phone' },
  { label: '职务 (身兼多职)', value: 'position' },
  { label: '归属单位/组织', value: 'company' },
  { label: '备注说明', value: 'notes' },
  { label: '入库时间', value: 'created_at' },
];

const MemberCenterPage: React.FC = () => {
  const [params, setParams] = useState<{ page: number; keyword: string; category_code?: string }>({ 
    page: 1, 
    keyword: '',
    category_code: undefined 
  });
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [selectedFields, setSelectedFields] = useState<string[]>(['name', 'phone', 'position', 'company']);
  const [exporting, setExporting] = useState(false);

  const { memberQuery, categoryQuery } = useMemberData(params);

  const memberColumns = [
    { 
      title: '姓名', 
      dataIndex: 'name', 
      key: 'name',
      render: (text: string) => <Text strong style={{ color: '#096dd9' }}>{text}</Text>
    },
    { 
      title: '职务与任职机构 (身兼多职)', 
      dataIndex: 'roles', 
      key: 'roles_m2m',
      render: (roles: any[]) => {
        if (!roles || roles.length === 0) return <Text type="secondary">暂无职务记录</Text>;
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {roles.map((r, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <Tag color={
                  r.category_code === 'company' ? 'blue' :
                  r.category_code === 'association' ? 'purple' :
                  r.category_code === 'office' ? 'orange' : 'cyan'
                } style={{ borderRadius: 4, margin: 0 }}>
                  {r.category_name}
                </Tag>
                <Text strong style={{ fontSize: 13, color: '#262626' }}>{r.org_name}</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>— {r.position || '职务暂缺'}</Text>
              </div>
            ))}
          </div>
        );
      }
    },
    { title: '联系电话', dataIndex: 'phone', key: 'phone' },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'} style={{ borderRadius: 4 }}>
          {status === 'active' ? '活跃' : '冻结'}
        </Tag>
      )
    },
  ];

  const handleTabChange = (key: string) => {
    setParams({
      ...params,
      category_code: key === 'all' ? undefined : key,
      page: 1
    });
  };

  const handleExport = async () => {
    if (selectedFields.length === 0) {
      message.warning('请至少选择一个导出的字段');
      return;
    }
    setExporting(true);
    try {
      const response = await apiClient.post(
        '/client/members/export/',
        { fields: selectedFields },
        {
          params: {
            keyword: params.keyword,
            category_code: params.category_code
          },
          responseType: 'blob'
        }
      );
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `会员数据导出_${new Date().toLocaleDateString().replace(/\//g, '-')}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      message.success('会员数据自定义导出成功！');
      setExportModalVisible(false);
    } catch (err) {
      console.error(err);
      message.error('导出 Excel 失败，请检查网络后重试');
    } finally {
      setExporting(false);
    }
  };

  const tabItems = [
    { label: '全部会员', key: 'all' },
    ...(categoryQuery.data || []).map(cat => ({
      label: cat.name,
      key: cat.code
    }))
  ];

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '10px 0' }}>
      <Card 
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <Space size="middle">
              <div style={{ 
                background: 'linear-gradient(135deg, #1890ff, #096dd9)', 
                padding: '8px 12px', 
                borderRadius: 8, 
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                boxShadow: '0 2px 8px rgba(24,144,255,0.2)'
              }}>
                <TeamOutlined style={{ fontSize: 18 }} />
              </div>
              <div>
                <Title level={4} style={{ margin: 0 }}>会员资源数据库</Title>
                <Text type="secondary" style={{ fontSize: 12 }}>检索已注册入库的全部企业机构与社会团体职务会员</Text>
              </div>
            </Space>
            <Button 
              type="primary" 
              icon={<DownloadOutlined />} 
              onClick={() => setExportModalVisible(true)}
              style={{ 
                height: 40, 
                borderRadius: 6, 
                fontWeight: 500,
                background: 'linear-gradient(135deg, #0b1d33, #1f3a60)',
                borderColor: '#0b1d33',
                boxShadow: '0 2px 6px rgba(11,29,51,0.15)'
              }}
            >
              自定义选择导出 Excel
            </Button>
          </div>
        }
        bordered={false}
        style={{ 
          borderRadius: 12, 
          boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
          border: '1px solid #f0f0f0'
        }}
      >
        <div style={{ marginBottom: 20 }}>
          <Input.Search 
            placeholder="在库中搜索会员姓名 / 任职机构 / 职务 / 电话..." 
            onSearch={(val) => setParams({ ...params, keyword: val, page: 1 })}
            allowClear
            size="large"
            enterButton="高级搜索"
            style={{ width: '100%', borderRadius: 8 }}
          />
        </div>

        <Tabs
          activeKey={params.category_code || 'all'}
          onChange={handleTabChange}
          items={tabItems}
          type="card"
          style={{ marginBottom: 16 }}
        />

        <Table
          dataSource={memberQuery.data?.results}
          columns={memberColumns}
          rowKey="id"
          loading={memberQuery.isLoading}
          pagination={{
            current: params.page,
            pageSize: 10,
            total: memberQuery.data?.count,
            onChange: (page) => setParams({ ...params, page }),
            showSizeChanger: false,
            position: ['bottomCenter']
          }}
          style={{ background: '#fff' }}
        />
      </Card>

      {/* 自定义选择导出 Modal */}
      <Modal
        title={
          <Space>
            <DownloadOutlined style={{ color: '#096dd9' }} />
            <span>自定义导出数据列选择</span>
          </Space>
        }
        open={exportModalVisible}
        onOk={handleExport}
        onCancel={() => setExportModalVisible(false)}
        okText="确认生成并下载"
        cancelText="取消"
        confirmLoading={exporting}
        destroyOnClose
        width={500}
        okButtonProps={{ 
          style: { background: 'linear-gradient(135deg, #0b1d33, #1f3a60)', borderColor: '#0b1d33' } 
        }}
      >
        <div style={{ margin: '12px 0 20px 0' }}>
          <Text type="secondary">您可以自主挑选本次导出 Excel 表格中包含的会员字段属性：</Text>
        </div>
        <div style={{ background: '#f5f5f5', padding: 20, borderRadius: 8, border: '1px solid #e8e8e8' }}>
          <Checkbox.Group 
            options={exportFields} 
            value={selectedFields} 
            onChange={(checkedValues) => setSelectedFields(checkedValues as string[])}
            style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
          />
        </div>
      </Modal>
    </div>
  );
};

export default MemberCenterPage;
