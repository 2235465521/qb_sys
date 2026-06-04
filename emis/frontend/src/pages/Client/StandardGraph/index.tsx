import React, { useState, useEffect, useRef } from 'react';
import { Card, Select, Button, Space, Typography, Spin, Empty, Alert } from 'antd';
import { SearchOutlined, InfoCircleOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import apiClient from '@/api/client';
import type { Standard, PaginatedResponse } from '@/types';

const { Text } = Typography;

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
  
  // 控制树枝逐渐展开的阶段：0-仅中心，1-展开一级引用，2-展开最新标准
  const [expandStage, setExpandStage] = useState<number>(0);
  const expandTimer1Ref = useRef<any>(null);
  const expandTimer2Ref = useRef<any>(null);

  // 联想输入选择器状态
  const [options, setOptions] = useState<{ value: number; label: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const timeoutRef = useRef<any>(null);

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
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (expandTimer1Ref.current) clearTimeout(expandTimer1Ref.current);
      if (expandTimer2Ref.current) clearTimeout(expandTimer2Ref.current);
    };
  }, []);

  // 根据选中ID拉取图谱
  const fetchGraph = async (id: number) => {
    setIsLoading(true);
    setError(null);
    setExpandStage(0);

    if (expandTimer1Ref.current) clearTimeout(expandTimer1Ref.current);
    if (expandTimer2Ref.current) clearTimeout(expandTimer2Ref.current);

    try {
      const { data } = await apiClient.get<GraphResponse>(`/client/standards/${id}/graph/`);
      setGraphData(data);

      // 模拟树枝缓慢依次生长：
      // 500ms 后展开第一级引用标准
      expandTimer1Ref.current = setTimeout(() => {
        setExpandStage(1);
      }, 500);

      // 2000ms 后展开第二级最新标准
      expandTimer2Ref.current = setTimeout(() => {
        setExpandStage(2);
      }, 2000);

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

  // 动态处理图谱数据并生成 ECharts Option，转换为径向树图(Radial Tree)
  const getOption = () => {
    if (!graphData || !graphData.nodes.length) return {};

    const rootNode = graphData.nodes.find(n => n.category === 0);
    if (!rootNode) return {};

    const treeData = {
      ...rootNode,
      symbolSize: 64, // 更大更圆润的中心节点
      itemStyle: {
        color: {
          type: 'radial',
          x: 0.5, y: 0.5, r: 0.5,
          colorStops: [
            { offset: 0, color: '#e0f2f1' },
            { offset: 0.7, color: '#26a69a' },
            { offset: 1, color: '#00695c' }
          ]
        },
        borderColor: '#80cbc4',
        borderWidth: 2,
        shadowBlur: 20,
        shadowColor: 'rgba(0, 150, 136, 0.6)'
      },
      label: {
        show: true,
        position: 'top',
        fontSize: 14,
        fontWeight: 'bold',
        color: '#004d40'
      },
      children: [] as any[]
    };

    const refNodes = graphData.nodes.filter(n => n.category === 1);
    
    if (expandStage >= 1) {
      refNodes.forEach(refNode => {
        const hasLatest = refNode.latest_standard_no && refNode.latest_standard_no !== refNode.name;
        
        const childNode: any = {
          ...refNode,
          symbolSize: 42,
          itemStyle: {
            color: {
              type: 'radial',
              x: 0.5, y: 0.5, r: 0.5,
              colorStops: [
                { offset: 0, color: '#e3f2fd' },
                { offset: 0.7, color: '#4fc3f7' },
                { offset: 1, color: '#0277bd' }
              ]
            },
            borderColor: '#81d4fa',
            borderWidth: 2,
            shadowBlur: 15,
            shadowColor: 'rgba(3, 169, 244, 0.4)'
          },
          children: []
        };

        if (hasLatest && expandStage >= 2) {
          childNode.children.push({
            name: refNode.latest_standard_no,
            id: `latest_${refNode.id}`,
            category: 2,
            title: '最新标准版本',
            type_display: refNode.type_display,
            status_display: '现行',
            company_name: '',
            latest_standard_no: refNode.latest_standard_no,
            symbolSize: 34,
            itemStyle: {
              color: {
                type: 'radial',
                x: 0.5, y: 0.5, r: 0.5,
                colorStops: [
                  { offset: 0, color: '#fff8e1' },
                  { offset: 0.7, color: '#ffca28' },
                  { offset: 1, color: '#ff8f00' }
                ]
              },
              borderColor: '#ffe082',
              borderWidth: 2,
              shadowBlur: 15,
              shadowColor: 'rgba(255, 179, 0, 0.5)'
            }
          });
        }
        treeData.children.push(childNode);
      });
    }

    return {
      title: {
        text: `${rootNode.name.replace(' (中心企标)', '')} 引用图谱`,
        subtext: '向外发散的树叶状关系网络。支持鼠标拖拽与滚轮缩放',
        top: 'bottom',
        left: 'right',
        textStyle: { fontSize: 14, color: '#006064' }
      },
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        backgroundColor: 'rgba(255, 255, 255, 0.96)',
        borderColor: '#00bcd4',
        borderWidth: 1,
        padding: [12, 16],
        textStyle: { color: '#333', fontSize: 12 },
        extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px;',
        formatter: (params: any) => {
          const data = params.data;
          const isCenter = data.category === 0;
          const isLatest = data.category === 2;
          
          let color = '#0288d1';
          if (isCenter) color = '#00796b';
          else if (isLatest) color = '#f57c00';
          
          return `
            <div style="font-weight: bold; margin-bottom: 8px; color: ${color}; font-size: 14px; border-bottom: 1px solid #f0f0f0; padding-bottom: 4px;">
              ${data.name} ${isCenter ? '(中心企标)' : (isLatest ? '(最新标准)' : '(引用标准)')}
            </div>
            <div style="margin-bottom: 4px;"><b>标准名称:</b> ${data.title || '--'}</div>
            <div style="margin-bottom: 4px;"><b>标准类型:</b> ${data.type_display || '--'}</div>
            <div style="margin-bottom: 4px;"><b>标准状态:</b> ${data.status_display || '--'}</div>
            ${data.company_name ? `<div style="margin-bottom: 4px;"><b>起草企业:</b> ${data.company_name}</div>` : ''}
            ${data.latest_standard_no ? `<div style="color: #fa8c16; font-weight: bold; margin-top: 6px; padding-top: 4px; border-top: 1px dashed #f0f0f0;"><b>最新标准号:</b> ${data.latest_standard_no}</div>` : ''}
          `;
        }
      },
      series: [
        {
          type: 'tree',
          data: [treeData],
          layout: 'radial',
          symbol: 'circle',
          roam: true,
          initialTreeDepth: 3, // 确保初始即完全展开计算
          animationDurationInitial: 1000, 
          animationEasingInitial: 'cubicOut',
          animationDurationUpdate: 1800, // 超长1.8秒顺滑发散生长更新动画，宛如枝叶随时间推移逐渐生长
          animationEasingUpdate: 'cubicInOut',
          lineStyle: {
            color: '#b3e5fc', // 优雅清爽的极浅科技蓝
            width: 1.5,       // 更细的线条，显得精致现代而不笨重
            curveness: 0.55   // 优美的曲线弧度
          },
          label: {
            position: 'outside',
            rotate: 'radial', // 沿着辐射方向旋转文字
            fontSize: 11,
            color: '#262626',
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            borderWidth: 1,
            borderColor: '#e8e8e8',
            padding: [4, 7],
            borderRadius: 6,
            shadowBlur: 6,
            shadowColor: 'rgba(0, 0, 0, 0.04)'
          },
          leaves: {
            label: {
              position: 'outside',
              rotate: 'radial'
            }
          }
        }
      ]
    };
  };

  return (
    <div className="standard-graph-page" style={{ padding: '4px' }}>
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
              key={`graph-chart-${selectedId}`}
              option={getOption()}
              style={{ height: '100%', width: '100%' }}
              theme="light"
            />
            {/* 说明小提示 */}
            <div style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(255,255,255,0.85)', padding: '6px 12px', borderRadius: 6, border: '1px solid #f0f0f0', display: 'flex', alignItems: 'center', gap: 6 }}>
              <InfoCircleOutlined style={{ color: '#00bcd4' }} />
              <span style={{ fontSize: 11, color: '#666' }}>中心企标呈青色球，规范性引用呈蓝色球，最新版本标准呈黄色球。</span>
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
