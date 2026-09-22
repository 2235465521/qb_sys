import React from 'react';
import { Drawer, List, Tag, Space, Typography, Empty } from 'antd';
import { FileTextOutlined, BankOutlined } from '@ant-design/icons';
import type { AssociationBatchItem } from '@/types';

const { Text } = Typography;

interface DetailDrawerProps {
  item: AssociationBatchItem | null;
  open: boolean;
  onClose: () => void;
}

export const DetailDrawer: React.FC<DetailDrawerProps> = ({ item, open, onClose }) => {
  if (!item) return null;

  const standards = item.standards || [];

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BankOutlined style={{ color: '#0d9488', fontSize: 18 }} />
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, color: '#0f172a' }}>{item.input_name}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              统一代码: {item.credit_code} {item.legal_person !== '-' && `| 法人: ${item.legal_person}`}
            </Text>
          </div>
        </div>
      }
      placement="right"
      width={600}
      open={open}
      onClose={onClose}
      bodyStyle={{ padding: '16px 24px' }}
    >
      <div style={{ marginBottom: 16, background: '#f8fafc', padding: 12, borderRadius: 8 }}>
        <Space size={8} wrap>
          <Tag color="cyan">标准总数: {item.standard_total}</Tag>
          <Tag color="blue">团体标准: {item.group_count}</Tag>
          <Tag color="green">国家标准: {item.national_count}</Tag>
          <Tag color="orange">地方标准: {item.local_count}</Tag>
          <Tag color="purple">行业标准: {item.industry_count}</Tag>
          {item.enterprise_count > 0 && <Tag color="geekblue">企业标准: {item.enterprise_count}</Tag>}
        </Space>
      </div>

      <List
        dataSource={standards}
        locale={{ emptyText: <Empty description="该社会团体暂未检索到关联标准记录" /> }}
        renderItem={(std) => {
          let tagColor = 'blue';
          if (std.type_display === '国家标准') tagColor = 'green';
          else if (std.type_display === '团体标准') tagColor = 'cyan';
          else if (std.type_display === '地方标准') tagColor = 'orange';

          return (
            <List.Item
              style={{
                padding: '12px 14px',
                marginBottom: 10,
                border: '1px solid #f1f5f9',
                borderRadius: 8,
                background: '#ffffff',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Space size={6}>
                    <FileTextOutlined style={{ color: '#0d9488' }} />
                    <Text strong style={{ fontSize: 14, color: '#1e293b' }}>
                      {std.standard_no}
                    </Text>
                    <Tag color={tagColor} style={{ fontSize: 11, borderRadius: 4 }}>
                      {std.type_display}
                    </Tag>
                  </Space>
                  <Tag color={std.status === '现行' ? 'success' : 'default'} style={{ margin: 0 }}>
                    {std.status}
                  </Tag>
                </div>

                <div style={{ marginTop: 6, fontSize: 13, color: '#334155' }}>
                  {std.title}
                </div>

                <div
                  style={{
                    marginTop: 8,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 12,
                    color: '#64748b',
                  }}
                >
                  <div>起草身份: <Text type="secondary">{std.drafter_display || '-'}</Text></div>
                  <div>发布: <Text type="secondary">{std.release_date || '-'}</Text></div>
                </div>
              </div>
            </List.Item>
          );
        }}
      />
    </Drawer>
  );
};
