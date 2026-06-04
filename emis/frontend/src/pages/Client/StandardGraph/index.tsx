import React, { useState, useEffect, useRef } from 'react';
import { Card, Select, Button, Space, Typography, Spin, Empty, Alert, Tooltip, message } from 'antd';
import { 
  SearchOutlined, ZoomInOutlined, ZoomOutOutlined, 
  CompressOutlined, FullscreenOutlined, FullscreenExitOutlined, 
  PictureOutlined, FilePdfOutlined, CheckCircleOutlined, WarningOutlined
} from '@ant-design/icons';
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
  
  const [expandStage, setExpandStage] = useState<number>(0);
  const expandTimer1Ref = useRef<any>(null);
  const expandTimer2Ref = useRef<any>(null);
  const expandTimer3Ref = useRef<any>(null);
  const expandTimer4Ref = useRef<any>(null);

  const [options, setOptions] = useState<{ value: number; label: string }[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const timeoutRef = useRef<any>(null);

  // ECharts 实例引用与容器 DOM 引用
  const echartsRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState<number>(1.05); // 稍微放大初始缩放，增加舒展度
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // 1. 缩放逻辑 (通过 ECharts Option 的 zoom 属性受控更新)
  const handleZoom = (type: 'in' | 'out') => {
    setZoom(prev => {
      const nextZoom = type === 'in' ? prev * 1.2 : prev / 1.2;
      return Math.min(Math.max(nextZoom, 0.3), 5); // 限制缩放区间
    });
  };

  // 2. 适应屏幕 (利用 ECharts 的 restore Action 实现平滑恢复，重置 React zoom 状态)
  const handleFitView = () => {
    if (echartsRef.current) {
      const chartInstance = echartsRef.current.getEchartsInstance();
      setZoom(1.05);
      chartInstance.dispatchAction({ type: 'restore' });
      message.success('视图已平滑重置并适应屏幕');
    }
  };

  // 3. 全屏操作 (基于 HTML5 Fullscreen API 与事件监听)
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => {
        setIsFullscreen(true);
      }).catch(err => {
        message.error(`无法进入全屏: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      const isCurrentlyFull = !!document.fullscreenElement;
      setIsFullscreen(isCurrentlyFull);
      if (echartsRef.current) {
        setTimeout(() => {
          echartsRef.current.getEchartsInstance().resize();
        }, 120);
      }
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // 4. 图片导出 (PNG)
  const handleExportPNG = () => {
    if (!echartsRef.current || !graphData?.nodes?.length) return;
    const chartInstance = echartsRef.current.getEchartsInstance();
    const centerNode = graphData.nodes.find(n => n.category === 0);
    const fileName = centerNode ? centerNode.name.replace(/\//g, '_') : '标准';
    
    const dataUrl = chartInstance.getDataURL({
      type: 'png',
      pixelRatio: 2.5,
      backgroundColor: '#ffffff'
    });

    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = `${fileName}_引用关系图谱.png`;
    link.click();
    message.success('图谱 PNG 图片已开始下载');
  };

  // 5. PDF 导出 (独立打印窗口流自适应输出)
  const handleExportPDF = () => {
    if (!echartsRef.current || !graphData?.nodes?.length) return;
    const chartInstance = echartsRef.current.getEchartsInstance();
    const centerNode = graphData.nodes.find(n => n.category === 0);
    const stdName = centerNode ? centerNode.name : '企业标准';

    const dataUrl = chartInstance.getDataURL({
      type: 'png',
      pixelRatio: 2.5,
      backgroundColor: '#ffffff'
    });

    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(`
        <html>
          <head>
            <title>${stdName} 规范引用知识图谱</title>
            <style>
              @page { size: landscape; margin: 0; }
              body { margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #ffffff; }
              img { max-width: 100%; max-height: 100%; object-fit: contain; }
              @media print {
                body { background-color: #ffffff; }
                img { width: 100vw; height: 100vh; object-fit: contain; }
              }
            </style>
          </head>
          <body>
            <img src="${dataUrl}" onload="setTimeout(function(){ window.print(); window.close(); }, 350);" />
          </body>
        </html>
      `);
      printWindow.document.close();
    }
  };

  // 6. 数据初始化与联想查询
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
      if (expandTimer3Ref.current) clearTimeout(expandTimer3Ref.current);
      if (expandTimer4Ref.current) clearTimeout(expandTimer4Ref.current);
    };
  }, []);

  const fetchGraph = async (id: number) => {
    setIsLoading(true);
    setError(null);
    setExpandStage(0);
    setZoom(1.05); // 切换标准重置缩放

    if (expandTimer1Ref.current) clearTimeout(expandTimer1Ref.current);
    if (expandTimer2Ref.current) clearTimeout(expandTimer2Ref.current);
    if (expandTimer3Ref.current) clearTimeout(expandTimer3Ref.current);
    if (expandTimer4Ref.current) clearTimeout(expandTimer4Ref.current);

    try {
      const { data } = await apiClient.get<GraphResponse>(`/client/standards/${id}/graph/`);
      setGraphData(data);

      // 阶段一：500ms 后，平滑伸展出第一级引用标准的枝干线条
      expandTimer1Ref.current = setTimeout(() => {
        setExpandStage(1);
      }, 500);

      // 阶段二：1700ms 后（给线条 1200ms 舒展空间），第一级节点的球体和标签文字如绿叶般绽放变大
      expandTimer2Ref.current = setTimeout(() => {
        setExpandStage(2);
      }, 1700);

      // 阶段三：3200ms 后（给第一级节点绽放预留 1500ms 稳定展示），继续向末梢伸展出第二级最新版本标准的线条
      expandTimer3Ref.current = setTimeout(() => {
        setExpandStage(3);
      }, 3200);

      // 阶段四：4400ms 后（给第二级线条 1200ms 舒展空间），第二级黄球和标签文字如金色花朵般破土绽放
      expandTimer4Ref.current = setTimeout(() => {
        setExpandStage(4);
      }, 4400);

    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.error || '拉取图谱数据失败，请重试');
      setGraphData(null);
    } finally {
      setIsLoading(false);
    }
  };

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

  // 7. 径向树图 ECharts Option 发生器 (Radial Tree Option Builder)
  const getOption = () => {
    if (!graphData || !graphData.nodes.length) return {};

    const rootNode = graphData.nodes.find(n => n.category === 0);
    if (!rootNode) return {};

    // 严密保留原始字符（连字符 & 破折号）进行结构化嵌套数据拼装
    const treeData: any = {
      id: rootNode.id,
      name: rootNode.name,
      symbolSize: 64,
      category: 0,
      title: rootNode.title,
      type_display: rootNode.type_display,
      status_display: rootNode.status_display,
      company_name: rootNode.company_name,
      itemStyle: {
        color: {
          type: 'radial', x: 0.4, y: 0.4, r: 0.6,
          colorStops: [
            { offset: 0, color: '#60a5fa' }, // 柔和星空蓝
            { offset: 0.8, color: '#1e40af' }, // 经典科技蓝
            { offset: 1, color: '#1e1b4b' }   // 深邃蓝底色
          ]
        },
        borderColor: 'rgba(96, 165, 250, 0.8)',
        borderWidth: 2.5,
        shadowBlur: 25,
        shadowColor: 'rgba(30, 64, 175, 0.45)' // 弥散暗蓝光晕
      },
      label: {
        show: true, position: 'top', fontSize: 13, fontWeight: 'bold', color: '#1e3a8a'
      },
      children: []
    };

    if (expandStage >= 1) {
      const refNodes = graphData.nodes.filter(n => n.category === 1);
      refNodes.forEach(n => {
        const hasLatest = n.latest_standard_no && n.latest_standard_no.trim() !== n.name.trim();
        
        // 判定第一层节点自身的显示状态
        const isFirstLayerBlooming = expandStage >= 2;
        
        const childNode: any = {
          id: n.id,
          name: n.name,
          symbolSize: isFirstLayerBlooming ? 42 : 0.001, // 线条先长（size接近0），之后变大绽放
          category: 1,
          title: n.title,
          type_display: n.type_display,
          status_display: n.status_display,
          company_name: n.company_name,
          latest_standard_no: n.latest_standard_no,
          itemStyle: {
            opacity: isFirstLayerBlooming ? 1 : 0, // 线条长出阶段球体透明，绽放后显现
            color: {
              type: 'radial', x: 0.5, y: 0.5, r: 0.5,
              colorStops: [
                { offset: 0, color: '#e3f2fd' },
                { offset: 0.7, color: '#2196f3' },
                { offset: 1, color: '#0d47a1' }
              ]
            },
            borderColor: '#90caf9',
            borderWidth: 2,
            shadowBlur: isFirstLayerBlooming ? 12 : 0,
            shadowColor: 'rgba(33, 150, 243, 0.4)'
          },
          label: {
            show: isFirstLayerBlooming // 绽放后才展示标签文字
          },
          children: []
        };

        // 第二层最新版本替代（黄球）
        if (hasLatest && expandStage >= 3) {
          const isSecondLayerBlooming = expandStage >= 4;
          childNode.children.push({
            id: `latest_${n.id}`,
            name: n.latest_standard_no,
            symbolSize: isSecondLayerBlooming ? 34 : 0.001, // 同理，最新版本线条先长，之后绽放
            category: 2,
            title: '替代最新标准版本',
            type_display: n.type_display,
            status_display: '现行',
            itemStyle: {
              opacity: isSecondLayerBlooming ? 1 : 0,
              color: {
                type: 'radial', x: 0.5, y: 0.5, r: 0.5,
                colorStops: [
                  { offset: 0, color: '#fff8e1' },
                  { offset: 0.7, color: '#ffc107' },
                  { offset: 1, color: '#ff6f00' }
                ]
              },
              borderColor: '#ffe082',
              borderWidth: 2,
              shadowBlur: isSecondLayerBlooming ? 10 : 0,
              shadowColor: 'rgba(255, 193, 7, 0.4)'
            },
            label: {
              show: isSecondLayerBlooming
            }
          });
        }
        treeData.children.push(childNode);
      });
    }

    return {
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        backgroundColor: 'rgba(255, 255, 255, 0.98)',
        borderColor: '#00bcd4',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: '#333', fontSize: 11 },
        extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-radius: 8px;',
        formatter: (params: any) => {
          const d = params.data;
          const isCenter = d.category === 0;
          const isLatest = d.category === 2;
          const label = isCenter ? '中心企标' : (isLatest ? '替代最新标准' : '规范引用标准');
          const color = isCenter ? '#00796b' : (isLatest ? '#e65100' : '#0d47a1');
          return `
            <div style="font-weight: bold; margin-bottom: 6px; color: ${color}; font-size: 13px; border-bottom: 1px solid #f0f0f0; padding-bottom: 4px;">
              ${d.name} (${label})
            </div>
            <div><b>标准名称:</b> ${d.title || '--'}</div>
            <div><b>标准类型:</b> ${d.type_display || '--'}</div>
            <div><b>标准状态:</b> ${d.status_display || '--'}</div>
            ${d.company_name ? `<div><b>起草企业:</b> ${d.company_name}</div>` : ''}
            ${d.latest_standard_no && d.latest_standard_no.trim() !== d.name.trim() ? `<div style="color: #d84315; font-weight: bold; margin-top: 4px; border-top: 1px dashed #eee; padding-top: 4px;"><b>已废止，替代标准:</b> ${d.latest_standard_no}</div>` : ''}
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
          zoom: zoom,
          initialTreeDepth: 3,
          // 精准分配画布四角留白，彻底封死超出卡片边缘的可能性
          top: '12%',
          bottom: '12%',
          left: '12%',
          right: '12%',
          // 2秒极致平滑的树枝绽放发散动效，让前台体验富有科技呼吸感
          animationDurationInitial: 1000,
          animationEasingInitial: 'cubicOut',
          animationDurationUpdate: 2000,
          animationEasingUpdate: 'cubicInOut',
          lineStyle: {
            color: 'rgba(144, 202, 249, 0.38)', // 优雅半透明星空蓝，降低线条杂乱感
            width: 1.5, // 纤细线条，更具科技感
            curveness: 0.15 // 极轻微优雅弯曲，避免菊花状折角
          },
          label: {
            position: 'outside',
            rotate: 'radial',
            fontSize: 9.5,
            fontWeight: 500,
            color: '#374151',
            textShadowColor: 'rgba(255, 255, 255, 0.95)',
            textShadowBlur: 4,
            padding: [2, 4],
            formatter: (params: any) => {
              const name = params.name;
              if (!name) return '';
              // 中心企标节点保持尊贵的单行水平排列，不进行年份换行
              if (params.data && params.data.category === 0) {
                return name;
              }
              // 匹配标准号末尾的破折号、连字符或冒号+4位年份，自动折行并括号化 (使用 $1 捕获组避免 TS 参数隐式 any 与未读取声明错误)
              const regex = /[-—:](\d{4})$/;
              if (regex.test(name)) {
                return name.replace(regex, '\n($1)');
              }
              return name;
            }
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

  // 8. 看板数据动态计算与严谨字符判定
  const getStats = () => {
    if (!graphData) return { total: 0, gbCount: 0, otherCount: 0, outdatedCount: 0 };
    const refNodes = graphData.nodes.filter(n => n.category === 1);
    
    let gbCount = 0;
    let otherCount = 0;
    let outdatedCount = 0;

    if (expandStage >= 2) {
      refNodes.forEach(n => {
        // 严格精确核对前缀格式，防止因连字符造成的错判
        const nameTrimmed = n.name.trim();
        const isGb = nameTrimmed.startsWith('GB') || nameTrimmed.startsWith('GB/T');
        if (isGb) {
          gbCount++;
        } else {
          otherCount++;
        }

        const hasLatest = n.latest_standard_no && n.latest_standard_no.trim() !== nameTrimmed;
        if (hasLatest && expandStage >= 4) {
          outdatedCount++;
        }
      });
    }

    return {
      total: refNodes.length,
      gbCount,
      otherCount,
      outdatedCount
    };
  };

  const stats = getStats();

  return (
    <div className="standard-graph-page" style={{ padding: '4px' }}>
      {/* 检索配置卡片 */}
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
              placeholder="请输入企业标准编号或名称检索（如: Q/XMBL）"
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

      {/* 图谱展示外包容器卡片 */}
      <div ref={containerRef} style={{ position: 'relative', width: '100%' }}>
        <Card
          bordered={false}
          style={{
            borderRadius: 12,
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.02)',
            border: '1px solid #f0f0f0',
            position: 'relative'
          }}
          bodyStyle={{ padding: isFullscreen ? '0' : '24px' }}
        >
          {isLoading ? (
            <div style={{ height: '70vh', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 16 }}>
              <Spin size="large" />
              <Text type="secondary">正在获取并分析标准层级，生成图谱中...</Text>
            </div>
          ) : error ? (
            <div style={{ padding: '24px 0', height: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Alert message="图谱拉取错误" description={error} type="error" showIcon style={{ maxWidth: 450 }} />
            </div>
          ) : graphData && graphData.nodes.length > 0 ? (
            <div style={{ height: isFullscreen ? '100vh' : '75vh', position: 'relative', background: '#ffffff', borderRadius: 12 }}>
              
              {/* 任务一：毛玻璃悬浮统计看板 (Floating Stats Card) */}
              <div 
                style={{
                  position: 'absolute',
                  top: 16,
                  left: 16,
                  zIndex: 10,
                  width: 256,
                  backdropFilter: 'blur(12px)',
                  WebkitBackdropFilter: 'blur(12px)', // 增强对 WebKit 浏览器的兼容
                  backgroundColor: 'rgba(255, 255, 255, 0.75)',
                  border: '1px solid rgba(255, 255, 255, 0.4)',
                  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
                  borderRadius: 16,
                  padding: 16,
                  transition: 'all 0.3s ease',
                  userSelect: 'none',
                  fontFamily: 'Inter, system-ui, sans-serif'
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 700, color: '#1f2937', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#009688' }}></span>
                  图谱引用数据分析
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: '#4b5563' }}>
                  <div>引用标准总数：<span style={{ fontWeight: 600, color: '#111827' }}>共引用 {stats.total} 项</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: 10 }}>
                    <span>• 国家标准(GB):</span>
                    <span style={{ fontWeight: 600 }}>{stats.gbCount} 项</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', paddingLeft: 10 }}>
                    <span>• 行标/其它标准:</span>
                    <span style={{ fontWeight: 600 }}>{stats.otherCount} 项</span>
                  </div>
                </div>

                {/* 健康度警告逻辑 */}
                <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.06)' }}>
                  {stats.outdatedCount > 0 ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#dc2626', fontSize: 11, fontWeight: 600 }}>
                      <WarningOutlined />
                      <span>存在 {stats.outdatedCount} 项已更新/替代标准</span>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#16a34a', fontSize: 11, fontWeight: 600 }}>
                      <CheckCircleOutlined />
                      <span>所有引用标准均为最新现行版本</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 核心 ECharts 树图组件 */}
              <ReactECharts
                ref={echartsRef}
                key={`graph-chart-${selectedId}`}
                option={getOption()}
                style={{ height: '100%', width: '100%' }}
                theme="light"
              />

              {/* 任务二：右下角悬浮操作工具栏 (Floating Toolbar) */}
              <div 
                style={{
                  position: 'absolute',
                  bottom: 16,
                  right: 16,
                  zIndex: 10,
                  display: 'flex',
                  gap: 8,
                  backgroundColor: 'rgba(255, 255, 255, 0.85)',
                  backdropFilter: 'blur(8px)',
                  WebkitBackdropFilter: 'blur(8px)',
                  border: '1px solid rgba(229, 231, 235, 0.6)',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.05)',
                  padding: '6px',
                  borderRadius: 12,
                  userSelect: 'none'
                }}
              >
                <Tooltip title="放大">
                  <Button type="text" icon={<ZoomInOutlined />} onClick={() => handleZoom('in')} />
                </Tooltip>
                <Tooltip title="缩小">
                  <Button type="text" icon={<ZoomOutOutlined />} onClick={() => handleZoom('out')} />
                </Tooltip>
                <Tooltip title="适应屏幕">
                  <Button type="text" icon={<CompressOutlined />} onClick={handleFitView} />
                </Tooltip>
                <Tooltip title={isFullscreen ? "退出全屏" : "全屏"}>
                  <Button type="text" icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />} onClick={toggleFullscreen} />
                </Tooltip>
                <div style={{ width: 1, background: '#e5e7eb', margin: '4px 2px' }}></div>
                <Tooltip title="导出图片">
                  <Button type="text" icon={<PictureOutlined />} onClick={handleExportPNG} />
                </Tooltip>
                <Tooltip title="导出 PDF">
                  <Button type="text" icon={<FilePdfOutlined />} onClick={handleExportPDF} />
                </Tooltip>
              </div>

            </div>
          ) : (
            <div style={{ height: '70vh', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无图谱数据。请在上方输入中心企标编号进行生成。" />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default StandardGraphPage;
