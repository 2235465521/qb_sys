import React, { useState, useMemo } from 'react';
import { Table, Tag, Typography, Button, Space, Input } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { BankOutlined, SearchOutlined, EyeOutlined } from '@ant-design/icons';
import type { AssociationBatchItem } from '@/types';

const { Text } = Typography;

interface SummaryTableProps {
  items: AssociationBatchItem[];
  selectedNames: string[];
  onSelectionChange: (names: string[]) => void;
  onViewDetails: (item: AssociationBatchItem) => void;
}

export const SummaryTable: React.FC<SummaryTableProps> = ({
  items,
  selectedNames,
  onSelectionChange,
  onViewDetails,
}) => {
  const [filterKeyword, setFilterKeyword] = useState('');

  const filteredItems = useMemo(() => {
    if (!filterKeyword.trim()) return items;
    const kw = filterKeyword.trim().toLowerCase();
    return items.filter(
      (it) =>
        it.input_name.toLowerCase().includes(kw) ||
        it.credit_code.toLowerCase().includes(kw) ||
        it.legal_person.toLowerCase().includes(kw) ||
        it.area.toLowerCase().includes(kw)
    );
  }, [items, filterKeyword]);

  const rowSelection = {
    selectedRowKeys: selectedNames,
    onChange: (keys: React.Key[]) => {
      onSelectionChange(keys as string[]);
    },
  };

  const columns: ColumnsType<AssociationBatchItem> = [
    {
      title: '序号',
      dataIndex: 'index',
      key: 'index',
      width: 65,
      align: 'center',
    },
    {
      title: '社团组织名称',
      dataIndex: 'input_name',
      key: 'input_name',
      ellipsis: true,
      render: (name: string) => (
        <Space size={4}>
          <BankOutlined style={{ color: '#0d9488' }} />
          <Text strong style={{ color: '#0f172a' }} ellipsis={{ tooltip: name }}>
            {name}
          </Text>
        </Space>
      ),
    },
    {
      title: '统一社会信用代码',
      dataIndex: 'credit_code',
      key: 'credit_code',
      width: 190,
      render: (code: string) => (
        <Text style={{ fontFamily: 'monospace', fontSize: 13 }}>
          {code || '-'}
        </Text>
      ),
    },
    {
      title: '法人',
      dataIndex: 'legal_person',
      key: 'legal_person',
      width: 90,
      align: 'center',
      render: (val: string) => val || '-',
    },
    {
      title: '所属地区',
      dataIndex: 'area',
      key: 'area',
      width: 140,
      ellipsis: true,
      render: (val: string) => val || '-',
    },
    {
      title: '团标数',
      dataIndex: 'group_count',
      key: 'group_count',
      width: 75,
      align: 'center',
      sorter: (a, b) => a.group_count - b.group_count,
      render: (cnt: number) => (
        <span style={{ fontWeight: cnt > 0 ? 600 : 400, color: cnt > 0 ? '#0d9488' : '#94a3b8' }}>
          {cnt}
        </span>
      ),
    },
    {
      title: '国标数',
      dataIndex: 'national_count',
      key: 'national_count',
      width: 75,
      align: 'center',
      sorter: (a, b) => a.national_count - b.national_count,
      render: (cnt: number) => (
        <span style={{ fontWeight: cnt > 0 ? 600 : 400, color: cnt > 0 ? '#16a34a' : '#94a3b8' }}>
          {cnt}
        </span>
      ),
    },
    {
      title: '地/行标',
      key: 'other_count',
      width: 80,
      align: 'center',
      render: (_, record) => {
        const sum = record.local_count + record.industry_count;
        return (
          <span style={{ fontWeight: sum > 0 ? 600 : 400, color: sum > 0 ? '#ea580c' : '#94a3b8' }}>
            {sum}
          </span>
        );
      },
    },
    {
      title: '标准总数',
      dataIndex: 'standard_total',
      key: 'standard_total',
      width: 100,
      align: 'center',
      sorter: (a, b) => a.standard_total - b.standard_total,
      render: (total: number, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => onViewDetails(record)}
          style={{
            fontWeight: 600,
            fontSize: 14,
            color: total > 0 ? '#0d9488' : '#94a3b8',
            padding: 0,
          }}
        >
          {total} 项
          {total > 0 && <EyeOutlined style={{ marginLeft: 4, fontSize: 12 }} />}
        </Button>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      align: 'center',
      render: (status: string, record) => {
        if (record.standard_total > 0) {
          return <Tag color="success">有标准资产</Tag>;
        }
        if (status === 'matched') {
          return <Tag color="default">库中有记录</Tag>;
        }
        return <Tag color="warning">暂未收录</Tag>;
      },
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text type="secondary" style={{ fontSize: 13 }}>
          已选择 <Text strong style={{ color: '#0d9488' }}>{selectedNames.length}</Text> / {items.length} 家社会团体
        </Text>

        <Input
          prefix={<SearchOutlined style={{ color: '#94a3b8' }} />}
          placeholder="在结果中过滤社团名称/代码/地区..."
          value={filterKeyword}
          onChange={(e) => setFilterKeyword(e.target.value)}
          allowClear
          style={{ width: 280, borderRadius: 16 }}
        />
      </div>

      <Table<AssociationBatchItem>
        rowKey="input_name"
        rowSelection={rowSelection}
        columns={columns}
        dataSource={filteredItems}
        pagination={{
          pageSize: 8,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 家社团组织`,
        }}
        size="middle"
        bordered
      />
    </div>
  );
};
