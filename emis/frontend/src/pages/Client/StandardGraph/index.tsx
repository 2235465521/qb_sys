import React, { useState, useEffect, useRef } from 'react';
import { Card, Select, Button, Space, Typography, Spin, Empty, Alert } from 'antd';
import { ClusterOutlined, SearchOutlined, InfoCircleOutlined } from '@ant-design/icons';
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
  
  // 动画阶段状态：0 - 中心聚合，1 - 一级引用向外生长，2 - 二级最新标准自一级分支向外展叶
  const [animationStage, setAnimationStage] = useState<number>(0);

  // 联想输入选择器状态
  const [options, setOptions] = useState<{ value: number; label: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const timeoutRef = useRef<any>(null);

  // 动画阶段定时器引用，防止异步内存泄漏和干扰
  const stageTimer1Ref = useRef<any>(null);
  const stageTimer2Ref = useRef<any>(null);

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
      if (stageTimer1Ref.current) clearTimeout(stageTimer1Ref.current);
      if (stageTimer2Ref.current) clearTimeout(stageTimer2Ref.current);
    };
  }, []);

  // 根据选中ID拉取图谱
  const fetchGraph = async (id: number) => {
    setIsLoading(true);
    setError(null);
    setAnimationStage(0); // 立即初始化为第0阶段

    // 清理之前的定时器
    if (stageTimer1Ref.current) clearTimeout(stageTimer1Ref.current);
    if (stageTimer2Ref.current) clearTimeout(stageTimer2Ref.current);

    try {
      const { data } = await apiClient.get<GraphResponse>(`/client/standards/${id}/graph/`);
      setGraphData(data);

      // 第一阶段：延时 60ms 触发一级节点向外生长，二级节点紧随其父节点移动
      stageTimer1Ref.current = setTimeout(() => {
        setAnimationStage(1);
      }, 60);

      // 第二阶段：延时 1100ms（此时一级节点已稳定），触发二级节点自一级节点向外“开花展叶”
      stageTimer2Ref.current = setTimeout(() => {
        setAnimationStage(2);
      }, 1100);

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

  // 动态处理图谱数据：增加二级引用（最新标准）节点与连线，计算扇叶化初始位置与 3D 特效
  const processedGraphData = React.useMemo(() => {
    if (!graphData) return null;

    const nodes = [...graphData.nodes];
    const links = [...graphData.links];
    const categories = [
      { name: '中心企标' },
      { name: '引用标准' },
      { name: '最新标准' }
    ];

    const existingNodeNames = new Set(nodes.map(n => n.name));

    // 扫描一级引用节点，若存在最新标准则添加二级引用节点及连线
    graphData.nodes.forEach(node => {
      if (node.category === 1 && node.latest_standard_no && node.latest_standard_no !== node.name) {
        const latestName = node.latest_standard_no;
        let latestId = '';

        const existingNode = nodes.find(n => n.name === latestName);
        if (existingNode) {
          latestId = existingNode.id;
        }

        if (!latestId) {
          latestId = `latest_${node.id}`;
          nodes.push({
            id: latestId,
            name: latestName,
            symbolSize: 32,
            category: 2,
            title: '最新标准版本',
            type_display: node.type_display,
            status_display: '现行',
            company_name: ''
          });
          existingNodeNames.add(latestName);
        }

        links.push({
          source: node.id,
          target: latestId,
          label: {
            show: true,
            formatter: '最新标准'
          }
        });
      }
    });

    const N1 = graphData.nodes.filter(n => n.category === 1).length;
    let category1Index = 0;

    // 计算入场时类似“树木枝叶向外萌芽”的轨迹坐标位置，并配置微光玻璃 3D 节点外观
    const processedNodes = nodes.map(node => {
      const isCenter = node.category === 0;

      let x = 300;
      let y = 300;
      let fixed = false;

      if (isCenter) {
        fixed = true; // 中心企标固定在正中央
      } else if (node.category === 1) {
        // 第一阶段（第1阶段及以后）一级引用节点开始从中心飞往它们的最终坐标
        if (animationStage >= 1) {
          const theta = (category1Index / N1) * 2 * Math.PI;
          x = 300 + 150 * Math.cos(theta); // 稍加扩大半径防拥挤
          y = 300 + 150 * Math.sin(theta);
        }
        category1Index++;
      } else if (node.category === 2) {
        // 二级最新标准节点：
        // 阶段0：全聚集在中心 (300, 300)
        // 阶段1：依附在它们的一级引用父节点位置（与父节点一起从中心飞到一级引用位置）
        // 阶段2：从一级引用位置飞往它们自己的最终二级外层“展叶”位置，形成二次发芽
        const parentLink = links.find(l => l.target === node.id);
        const parentNode = parentLink ? nodes.find(n => n.id === parentLink.source) : null;
        const parentIndex = parentNode ? graphData.nodes.filter(n => n.category === 1).findIndex(n => n.id === parentNode.id) : 0;
        const parentTheta = (parentIndex / N1) * 2 * Math.PI;

        if (animationStage === 1) {
          // 阶段1：处于一级节点位置
          x = 300 + 150 * Math.cos(parentTheta);
          y = 300 + 150 * Math.sin(parentTheta);
        } else if (animationStage === 2) {
          // 阶段2：从一级节点向外发散，萌芽出第二级树叶
          const theta = parentTheta + 0.35; // 偏转角度形成优雅的枝叶发散效果
          x = 300 + 260 * Math.cos(theta);
          y = 300 + 260 * Math.sin(theta);
        }
      }

      // 设置节点尺寸，保证圆滑丰满
      let symbolSize = 30;
      if (isCenter) symbolSize = 54;
      else if (node.category === 1) symbolSize = 38;
      else if (node.category === 2) symbolSize = 30;

      return {
        ...node,
        x,
        y,
        fixed,
        symbolSize,
        itemStyle: {
          // 微光渐变与高饱和发光描边 (玻璃态质感，比生硬 3D 更加现代、圆滑)
          color: isCenter
            ? {
                type: 'linear',
                x: 0, y: 0, x2: 1, y2: 1,
                colorStops: [
                  { offset: 0, color: '#e0f2f1' },
                  { offset: 1, color: '#00b0ff' } // 亮眼科技蓝绿
                ]
              }
            : (node.category === 1
                ? {
                    type: 'linear',
                    x: 0, y: 0, x2: 1, y2: 1,
                    colorStops: [
                      { offset: 0, color: '#e6f7ff' },
                      { offset: 1, color: '#1890ff' } // 引用蓝
                    ]
                  }
                : {
                    type: 'linear',
                    x: 0, y: 0, x2: 1, y2: 1,
                    colorStops: [
                      { offset: 0, color: '#fffbe6' },
                      { offset: 1, color: '#fadb14' } // 警示金黄
                    ]
                  }
              ),
          borderColor: isCenter ? '#00e5ff' : (node.category === 1 ? '#40a9ff' : '#ffe58f'),
          borderWidth: isCenter ? 3.5 : 2,
          shadowBlur: isCenter ? 25 : 15,
          shadowColor: isCenter ? 'rgba(0, 229, 255, 0.4)' : (node.category === 1 ? 'rgba(24, 144, 255, 0.3)' : 'rgba(250, 219, 20, 0.45)'),
          shadowOffsetX: 0,
          shadowOffsetY: 0
        }
      };
    });

    const processedLinks = links.map(link => {
      const isLatest = link.label?.formatter === '最新标准';
      return {
        ...link,
        lineStyle: {
          color: isLatest ? '#ffe58f' : '#91d5ff',
          width: 2.5,
          type: 'solid',
          curveness: isLatest ? 0.2 : 0.08
        },
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [4, 9]
      };
    });

    return { nodes: processedNodes, links: processedLinks, categories };
  }, [graphData, animationStage]);

  // ECharts 图表配置
  const getOption = () => {
    if (!processedGraphData) return {};

    return {
      title: {
        text: `${processedGraphData.nodes[0].name.replace(' (中心企标)', '')} 引用图谱`,
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
            const isLatest = data.category === 2;
            
            let color = '#1890ff';
            if (isCenter) color = '#00838f';
            else if (isLatest) color = '#d48806';
            
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
          return `关系: <b>${params.data.label?.formatter || '规范性引用'}</b>`;
        }
      },
      legend: [
        {
          data: ['中心企标', '引用标准', '最新标准'],
          orient: 'vertical',
          left: 'left',
          top: 'top',
          textStyle: {
            color: '#333',
            fontWeight: 500
          }
        }
      ],
      // 扇叶与开花：设置慢速顺次入场延迟动画与缓动特效
      animationDuration: 2500,       // 延长至 2.5 秒，使开花飞出过渡极佳
      animationEasing: 'cubicInOut', // 丝滑柔和缓动
      animationDelay: (idx: number) => idx * 120, // 顺次慢速开花展开
      series: [
        {
          type: 'graph',
          layout: 'none', // 使用自定义预计算的扇形坐标系统，摆脱 force 的杂乱无章与无序抖动
          data: processedGraphData.nodes,
          links: processedGraphData.links,
          categories: processedGraphData.categories,
          roam: true,
          draggable: true, // 允许用户在 static 布局下自由拖拽节点排版
          label: {
            show: true,
            position: 'right',
            formatter: '{b}',
            fontSize: 11,
            color: '#262626',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            fontWeight: 500,
            // 现代气泡卡片标签样式，高雅精致
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            borderWidth: 1,
            borderColor: '#e8e8e8',
            padding: [4, 7],
            borderRadius: 6,
            shadowBlur: 6,
            shadowColor: 'rgba(0, 0, 0, 0.04)'
          },
          edgeLabel: {
            show: true,
            position: 'middle',
            formatter: (params: any) => {
              return params.data.label?.formatter || '';
            },
            fontSize: 9,
            color: '#8c8c8c'
          },
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
