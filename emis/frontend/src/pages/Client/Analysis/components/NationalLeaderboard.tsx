import React, { useState } from "react";
import { Card, Table, Typography, Statistic, Space, Select, Button, message } from "antd";
import { TrophyOutlined, BarChartOutlined, ArrowUpOutlined, FileExcelOutlined } from "@ant-design/icons";
import apiClient from "@/api/client";

const { Text } = Typography;

interface NationalLeaderboardProps {
  data: any[];
  loading: boolean;
}

const NationalLeaderboard: React.FC<NationalLeaderboardProps> = ({
  data,
  loading,
}) => {
  const [exportLimit, setExportLimit] = useState(10);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await apiClient.get(`/client/analysis/export-excel/`, {
        params: { limit: exportLimit },
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `国标热度排行_Top${exportLimit}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      message.success(`成功导出前 ${exportLimit} 条国标引用排行`);
    } catch (err) {
      console.error(err);
      message.error('导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  // 注入全局唯一排名以在跨页分页时保持稳定排序
  const mappedData = React.useMemo(() => {
    return (data || []).map((item, idx) => ({
      ...item,
      rank: idx + 1,
    }));
  }, [data]);

  const columns = [
    {
      title: "排名",
      dataIndex: "rank",
      key: "rank",
      width: 80,
      render: (rank: number) => (
        <span
          style={{
            fontSize: 16,
            fontWeight: "bold",
            color: rank <= 3 ? "#fadb14" : "#bfbfbf",
          }}
        >
          {rank}
        </span>
      ),
    },
    {
      title: "标准号",
      dataIndex: "standard_no",
      key: "standard_no",
      render: (text: string) => (
        <Text strong style={{ fontFamily: "Courier New, monospace" }}>
          {text}
        </Text>
      ),
    },
    {
      title: (
        <Space size={4}>
          <span>最新标准号</span>
          <ArrowUpOutlined style={{ color: '#52c41a', fontSize: 13 }} />
        </Space>
      ),
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (text: string) => (
        <Text style={{ fontFamily: "Courier New, monospace", color: '#595959' }}>
          {text || '--'}
        </Text>
      ),
    },
    {
      title: "被引用次数",
      dataIndex: "citation_count",
      key: "citation_count",
      width: 130,
      render: (count: number) => (
        <Statistic
          value={count}
          valueStyle={{ color: "#3f8600", fontSize: 18, fontWeight: "bold" }}
          prefix={<BarChartOutlined style={{ fontSize: 14 }} />}
        />
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <TrophyOutlined style={{ color: "#fadb14", fontSize: 18 }} />
          <span style={{ fontWeight: "bold" }}>国标引用热度排行榜</span>
        </Space>
      }
      extra={
        <Space>
          <Select
            value={exportLimit}
            onChange={(val) => setExportLimit(val)}
            style={{ width: 110 }}
            options={[
              { value: 10, label: "前 10 条" },
              { value: 20, label: "前 20 条" },
              { value: 30, label: "前 30 条" },
              { value: 50, label: "前 50 条" },
              { value: 100, label: "前 100 条" },
            ]}
          />
          <Button
            type="primary"
            icon={<FileExcelOutlined />}
            onClick={handleExport}
            loading={exporting}
          >
            导出 Excel
          </Button>
        </Space>
      }
      bordered={false}
      style={{
        borderRadius: 16,
        boxShadow: "0 6px 20px rgba(0,0,0,0.04)",
        border: "1px solid #f0f0f0",
        background: "#fff",
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
      bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column' }}
    >
      <Table
        dataSource={mappedData}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ showQuickJumper: true,
          pageSize: 10,
          showSizeChanger: false,
          showTotal: (total) => `共计 ${total} 条高频引用国标`,
        }}
        size="middle"
        bordered
        style={{ borderRadius: 8, overflow: "hidden" }}
      />
    </Card>
  );
};

export default NationalLeaderboard;
