import React, { useState } from "react";
import { Card, Table, Typography, Statistic, Space, Select, Button, message, Tooltip } from "antd";
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
      render: (rank: number) => {
        const isTop3 = rank <= 3;
        const top3Colors = [
          { border: '#fef08a', bg: 'linear-gradient(135deg, #fef08a 0%, #eab308 100%)', text: '#854d0e' }, // Gold
          { border: '#cbd5e1', bg: 'linear-gradient(135deg, #f8fafc 0%, #cbd5e1 100%)', text: '#334155' }, // Silver
          { border: '#fed7aa', bg: 'linear-gradient(135deg, #ffedd5 0%, #ca8a04 100%)', text: '#713f12' }  // Bronze
        ];
        
        if (isTop3) {
          const styleConfig = top3Colors[rank - 1];
          return (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 26,
                height: 26,
                borderRadius: '50%',
                background: styleConfig.bg,
                color: styleConfig.text,
                border: `1px solid ${styleConfig.border}`,
                fontSize: 13,
                fontWeight: 'bold',
                boxShadow: '0 2px 4px rgba(0,0,0,0.06)'
              }}
            >
              {rank}
            </span>
          );
        }
        
        return (
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 26,
              height: 26,
              fontSize: 13,
              fontWeight: 'bold',
              color: '#94a3b8',
            }}
          >
            {rank}
          </span>
        );
      },
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
      ellipsis: { showTitle: false },
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft" color="rgba(0,0,0,0.85)">
          <Text style={{ fontFamily: "Courier New, monospace", color: '#595959', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {text || '--'}
          </Text>
        </Tooltip>
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
          <TrophyOutlined style={{ color: "#eab308", fontSize: 18 }} />
          <span style={{ fontWeight: 600, color: '#0f172a' }}>国标引用热度排行榜</span>
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
            style={{
              background: 'linear-gradient(135deg, #0d9488 0%, #0f766e 100%)',
              borderColor: '#0d9488',
              boxShadow: '0 4px 10px rgba(13, 148, 120, 0.15)'
            }}
          >
            导出 Excel
          </Button>
        </Space>
      }
      bordered={false}
      className="fade-in-up"
      style={{
        borderRadius: 16,
        boxShadow: "0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)",
        border: "1px solid #f1f5f9",
        background: "#fff",
        height: '100%',
        display: 'flex',
        flexDirection: 'column'
      }}
      bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '16px 20px' }}
    >
      <Table
        dataSource={mappedData}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ showQuickJumper: true,
          pageSize: 12,
          showSizeChanger: false,
          showTotal: (total) => `共计 ${total} 条高频引用国标`,
        }}
        size="middle"
        style={{ borderRadius: 12, overflow: "hidden", border: '1px solid #f1f5f9' }}
      />
    </Card>
  );
};

export default NationalLeaderboard;
