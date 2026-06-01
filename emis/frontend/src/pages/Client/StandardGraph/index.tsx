import React, { useState, useEffect, useRef } from 'react';
import { Card, Select, Button, Space, Typography, Spin, Empty, Alert } from 'antd';
import { ClusterOutlined, SearchOutlined, InfoCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import apiClient from '@/api/client';
import type { Standard, PaginatedResponse } from '@/types';

const { Title, Paragraph, Text } = Typography;

interface GraphNode {
  id: string;
  name: string;
  symbolSize: number;
  category: number;
  title?: string;
  type_display?: string;
  status_display?: string;
  company_name?: string;
  latest_standard_no?: string;
}

interface GraphLink {
  source: string;
  target: string;
  label?: {
    show: boolean;
    formatter: string;
  };
}

interface GraphResponse {
  nodes: GraphNode[];
  links: GraphLink[];
  categories: { name: string }[];
}

const StandardGraphPage: React.FC = () => {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [graphData, setGraphData] = useState<GraphResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 联想输入选择器状态
  const [options, setOptions] = useState<{ value: number; label: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // 挂载时加载默认首个企标作为展示数据
  useEffect(() => {
    const loadDefaultStandard = async () => {
      setIsLoading(true);
      try {
        const { data } = await apiClient.get<PaginatedResponse<Standard>>('/client/standards/', {
          params: { page: 1, type: 'enterprise' }
        });
        if (data.results && data.results.length > 0) {
          const firstStd = data.results[0];
          setSelectedId(firstStd.id);
          // 将其放入联想候选以使搜索框有默认展示值
          setOptions([{
            value: firstStd.id,
            label: `${firstStd.standard_no} | ${firstStd.title || '无名称'}`
          }]);
          fetchGraph(firstStd.id);
        } else {
          setIsLoading(false);
        }
      } catch (err) {
        console.error(err);
        setError('加载默认标准失败，请手动检索查询。');
        setIsLoading(false);
      }
    };
    loadDefaultStandard();

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // 根据选中ID拉取图谱
  const fetchGraph = async (id: number) => {
    setIsLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<GraphResponse>(`/client/standards/${id}/graph/`);
      setGraphData(data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.error || '拉取图谱数据失败，请重试');
      setGraphData(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Autocomplete 动态异步联想搜索
  const handleSearch = (value: string) => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    
    const term = value.trim();
    if (!term) {
      setOptions([]);
      return;
    }

    setSearchLoading(true);
    timeoutRef.current = setTimeout(async () => {
      try {
        const { data } = await apiClient.get<PaginatedResponse<Standard>>('/client/standards/', {
          params: { keyword: term, type: 'enterprise' }
        });
        const items = (data.results || []).map(item => ({
          value: item.id,
          label: `${item.standard_no} | ${item.title || '无名称'} (${item.company_name || '无企业'})`
        }));
        setOptions(items);
      } catch (err) {
        console.error(err);
      } finally {
        setSearchLoading(false);
      }
    }, 450);
  };

  const handleSelect = (value: number) => {
    setSelectedId(value);
  };

  const executeSearch = () => {
    if (selectedId) {
      fetchGraph(selectedId);
    }
  };

  // ECharts 图表配置
  const getOption = () => {
    if (!graphData) return {};

    return {
      title: {
        text: `${graphData.nodes[0].name.replace(' (中心企标)', '')} 引用图谱`,
        subtext: '点击节点查看明细，支持鼠标拖拽与滚轮缩放',
        top: 'bottom',
        left: 'right',
        textStyle: {
          fontSize: 14,
          color: '#006064'
        }
      },
      tooltip: {
        trigger: 'item',
        enterable: true,
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#00bcd4',
        borderWidth: 1,
        padding: [12, 16],
        textStyle: {
          color: '#333',
          fontSize: 12,
          fontFamily: 'system-ui, sans-serif'
        },
        extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px; pointer-events: auto;',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const data = params.data;
            const isCenter = data.category === 0;
            return `
              <div style="font-weight: bold; margin-bottom: 8px; color: ${isCenter ? '#00838f' : '#1890ff'}; font-size: 14px; border-bottom: 1px solid #f0f0f0; padding-bottom: 4px;">
                ${data.name}
              </div>
              <div style="margin-bottom: 4px;"><b>标准名称:</b> ${data.title || '--'}</div>
              <div style="margin-bottom: 4px;"><b>标准类型:</b> ${data.type_display || '--'}</div>
              <div style="margin-bottom: 4px;"><b>标准状态:</b> ${data.status_display || '--'}</div>
              <div style="margin-bottom: 4px;"><b>起草企业:</b> ${data.company_name || '--'}</div>
              ${data.latest_standard_no ? `<div style="color: #fa8c16; font-weight: bold; margin-top: 6px; padding-top: 4px; border-top: 1px dashed #f0f0f0;"><b>最新标准号:</b> ${data.latest_standard_no}</div>` : ''}
            `;
          }
          return `关系: <b>${params.name || '规范性引用'}</b>`;
        }
      },
      legend: [
        {
          data: ['中心企标', '引用标准'],
          orient: 'vertical',
          left: 'left',
          top: 'top',
          textStyle: {
            color: '#333',
            fontWeight: 500
          }
        }
      ],
      animationDuration: 1200,
      animationEasingUpdate: 'quinticInOut',
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: graphData.nodes.map(node => {
            // 中心节点和普通节点渐变颜色配置
            const isCenter = node.category === 0;
            return {
              ...node,
              itemStyle: {
                color: isCenter 
                  ? {
                      type: 'radial',
                      x: 0.4, y: 0.4, r: 0.8,
                      colorStops: [
                        { offset: 0, color: '#00e5ff' },
                        { offset: 1, color: '#00838f' }
                      ]
                    }
                  : {
                      type: 'radial',
                      x: 0.4, y: 0.4, r: 0.8,
                      colorStops: [
                        { offset: 0, color: '#69c0ff' },
                        { offset: 1, color: '#1890ff' }
                      ]
                    },
                shadowBlur: 10,
                shadowColor: isCenter ? 'rgba(0,131,143,0.3)' : 'rgba(24,144,255,0.2)'
              }
            };
          }),
          links: graphData.links,
          categories: [
            { name: '中心企标' },
            { name: '引用标准' }
          ],
          roam: true,
          label: {
            show: true,
            position: 'right',
            formatter: '{b}',
            fontSize: 11,
            color: '#434343',
            fontFamily: 'Courier New, monospace',
            fontWeight: 'bold',
            backgroundColor: 'rgba(255,255,255,0.7)',
            padding: [2, 4],
            borderRadius: 4
          },
          force: {
            repulsion: 650,
            edgeLength: 160,
            gravity: 0.08,
            layoutAnimation: true
          },
          lineStyle: {
            color: '#b3d4fc',
            width: 2,
            curveness: 0.08
          },
          edgeSymbol: ['none', 'arrow'],
          edgeSymbolSize: [4, 8],
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 4,
              color: '#096dd9'
            },
            label: {
              fontSize: 12,
              backgroundColor: '#fff',
              borderWidth: 1,
              borderColor: '#096dd9'
            }
          }
        }
      ]
    };
  };

  return (
    <div className="standard-graph-page" style={{ padding: '4px' }}>
      {/* 渐变标题 Banner */}
      <div 
        style={{ 
          marginBottom: 20, 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          background: 'linear-gradient(135deg, #e0f2f1 0%, #b2dfdb 100%)',
          padding: '16px 24px',
          borderRadius: 12,
          boxShadow: '0 4px 15px rgba(0,0,0,0.02)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ background: '#009688', padding: 8, borderRadius: 8, color: '#fff', display: 'flex', alignItems: 'center' }}>
            <ClusterOutlined style={{ fontSize: 20 }} />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, color: '#004d40', fontWeight: 'bold' }}>标准知识图谱</h2>
            <p style={{ margin: 0, fontSize: 12, color: '#00796b' }}>
              通过数据挖掘与可视化关系网络，直观探寻本系统内企业标准与其对应引用国标/行标之间的关联体系结构。
            </p>
          </div>
        </div>
      </div>

      {/* 检索卡片 */}
      <Card
        bordered={false}
        style={{
          background: 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(8px)',
          borderRadius: 12,
          marginBottom: 16,
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.03)',
          border: '1px solid rgba(230, 230, 230, 0.6)'
        }}
        bodyStyle={{ padding: '16px 24px' }}
      >
        <Space size="middle" style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 320 }}>
            <span style={{ fontSize: 14, fontWeight: 'bold', color: '#004d40', whiteSpace: 'nowrap' }}>中心企标：</span>
            <Select
              showSearch
              placeholder="请输入企业标准编号或名称检索（支持联想输入，如: Q/XMBL, 电路板）"
              style={{ width: '100%', minWidth: 280 }}
              defaultActiveFirstOption={false}
              showArrow={false}
              filterOption={false}
              onSearch={handleSearch}
              onChange={handleSelect}
              notFoundContent={searchLoading ? <Spin size="small" /> : null}
              options={options}
              loading={searchLoading}
              value={selectedId || undefined}
            />
          </div>
          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={executeSearch}
            disabled={!selectedId}
            style={{
              borderRadius: 8,
              fontWeight: 500,
              background: 'linear-gradient(135deg, #009688 0%, #00796b 100%)',
              borderColor: '#009688',
              boxShadow: '0 4px 10px rgba(0, 150, 136, 0.2)'
            }}
          >
            生成知识图谱
          </Button>
        </Space>
      </Card>

      {/* 图谱展示区域 */}
      <Card
        bordered={false}
        style={{
          borderRadius: 12,
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.02)',
          border: '1px solid #f0f0f0',
          position: 'relative'
        }}
      >
        {isLoading ? (
          <div style={{ height: '70vh', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 16 }}>
            <Spin size="large" />
            <Text type="secondary">正在获取并分析标准引用层级，生成可视化图谱中...</Text>
          </div>
        ) : error ? (
          <div style={{ padding: '24px 0', height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Alert
              message="图谱拉取错误"
              description={error}
              type="error"
              showIcon
              style={{ maxWidth: 450 }}
            />
          </div>
        ) : graphData && graphData.nodes.length > 0 ? (
          <div style={{ height: '75vh', position: 'relative' }}>
            <ReactECharts
              option={getOption()}
              style={{ height: '100%', width: '100%' }}
              theme="light"
            />
            {/* 说明小提示 */}
            <div style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(255,255,255,0.85)', padding: '6px 12px', borderRadius: 6, border: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <InfoCircleOutlined style={{ color: '#00bcd4' }} />
              <span style={{ fontSize: 11, color: '#666' }}>中心企标呈青色大球，所引用的国标/行标呈蓝色小球。</span>
            </div>
          </div>
        ) : (
          <div style={{ height: '70vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无图谱数据。请在上方输入中心企标编号进行生成。"
            />
          </div>
        )}
      </Card>
    </div>
  );
};

export default StandardGraphPage;
