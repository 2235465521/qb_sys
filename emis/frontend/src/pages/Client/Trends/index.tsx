import React, { useState } from 'react';
import { Row, Col, Card, Typography, Select, Spin, Empty, Tag, Modal, Button, message } from 'antd';
import { RadarChartOutlined, FireOutlined, RiseOutlined, EnvironmentOutlined, FileTextOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import 'echarts-wordcloud';
import { useTrendData } from '@/hooks/useTrendData';

const { Title } = Typography;

const TrendDashboard: React.FC = () => {
  const [days, setDays] = useState<number>(30);
  const [selectedKeyword, setSelectedKeyword] = useState<string>('');
  const [reportVisible, setReportVisible] = useState<boolean>(false);

  const { wordCloudQuery, growthQuery, regionalQuery } = useTrendData(days, selectedKeyword);

  // Initialize selected keyword to the top trending word once data loads
  React.useEffect(() => {
    if (wordCloudQuery.data && wordCloudQuery.data.length > 0 && !selectedKeyword) {
      setSelectedKeyword(wordCloudQuery.data[0].name);
    }
  }, [wordCloudQuery.data, selectedKeyword]);

  // Dynamic Word Cloud Data mapping to highlight the selected word
  const wordCloudData = (wordCloudQuery.data || []).map(item => {
    const isSelected = item.name === selectedKeyword;
    return {
      name: item.name,
      value: item.value,
      textStyle: isSelected ? {
        fontWeight: 'bold',
        color: '#ff4d4f', // Dynamic selected glow color
        shadowBlur: 25,
        shadowColor: '#ff4d4f',
        fontSize: Math.max(30, item.value * 1.5) // Make it stand out
      } : {
        fontWeight: 'normal',
        color: 'rgb(' + [
          Math.round(Math.random() * 130),
          Math.round(Math.random() * 130),
          Math.round(Math.random() * 130)
        ].join(',') + ')'
      }
    };
  });

  const wordCloudOption = {
    tooltip: { 
      show: true,
      formatter: '关联企标数量: <b>{c}</b> 项'
    },
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      keepAspect: false,
      left: 'center',
      top: 'center',
      width: '95%',
      height: '95%',
      right: null,
      bottom: null,
      sizeRange: [14, 60],
      rotationRange: [-45, 45],
      rotationStep: 15,
      gridSize: 10,
      drawOutOfBound: false,
      emphasis: {
        textStyle: { 
          shadowBlur: 15, 
          shadowColor: '#1677ff',
          fontWeight: 'bold'
        }
      },
      data: wordCloudData
    }]
  };

  const onWordClick = (e: any) => {
    setSelectedKeyword(e.name);
  };

  const onChartReady = (instance: any) => {
    // Enable pointer cursor style on word hover
    instance.on('mouseover', (params: any) => {
      if (params.componentType === 'series') {
        instance.getZr().setCursorStyle('pointer');
      }
    });
    instance.on('mouseout', () => {
      instance.getZr().setCursorStyle('default');
    });
  };

  const growthData = (growthQuery.data || []).slice().reverse();

  const growthOption = {
    tooltip: { 
      trigger: 'axis', 
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const item = params[0];
        const rawItem = growthData[item.dataIndex];
        if (!rawItem) return '';
        const growthStr = rawItem.growth_rate >= 1000 ? '新晋爆发' : `+${rawItem.growth_rate}%`;
        return `${rawItem.keyword}<br/>环比增速: <b>${growthStr}</b><br/>本期申报标准数: <b>${rawItem.current_count}</b> 项`;
      }
    },
    grid: { left: '3%', right: '25%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', name: '本期申报数 (项)' },
    yAxis: {
      type: 'category',
      data: growthData.map(item => item.keyword),
      axisLabel: { 
        fontWeight: 'bold',
        interval: 0 // Force display all labels, prevent auto-hiding
      }
    },
    series: [
      {
        name: '本期申报数',
        type: 'bar',
        data: growthData.map(item => item.current_count),
        itemStyle: {
          color: '#ff4d4f',
          borderRadius: [0, 4, 4, 0]
        },
        label: {
          show: true,
          position: 'right',
          formatter: (params: any) => {
            const item = growthData[params.dataIndex];
            if (!item) return '';
            const rateStr = item.growth_rate >= 1000 ? '新晋爆发' : `+${item.growth_rate}%`;
            return `${rateStr} (${item.current_count}项)`;
          },
          fontWeight: 'bold',
          color: '#333'
        }
      }
    ]
  };

  // Sort and process all provinces without '其他地区' grouping
  const rawData = regionalQuery.data || [];
  const sortedData = [...rawData].sort((a, b) => b.count - a.count);
  const chartData = sortedData.map(item => ({ name: item.province, value: item.count }));
  const totalCount = sortedData.reduce((sum, item) => sum + item.count, 0);

  // Unified color palette: chartColors for 3D gradients, listColors for list dot matching
  const chartColors = [
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#69b1ff' }, { offset: 1, color: '#1677ff' }] // 3D Blue
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#95de64' }, { offset: 1, color: '#52c41a' }] // 3D Green
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ffd591' }, { offset: 1, color: '#fa8c16' }] // 3D Orange
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ff9c6e' }, { offset: 1, color: '#fa541c' }] // 3D Red-Orange
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ff85c0' }, { offset: 1, color: '#eb2f96' }] // 3D Pink
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#b37feb' }, { offset: 1, color: '#722ed1' }] // 3D Purple
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#85a5ff' }, { offset: 1, color: '#2f54eb' }] // 3D Indigo
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#5cdbd3' }, { offset: 1, color: '#13c2c2' }] // 3D Cyan
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ffec3d' }, { offset: 1, color: '#fadb14' }] // 3D Yellow
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ff7875' }, { offset: 1, color: '#f5222d' }] // 3D Red
    }
  ];

  const listColors = [
    '#1677ff', '#52c41a', '#fa8c16', '#fa541c', '#eb2f96',
    '#722ed1', '#2f54eb', '#13c2c2', '#fadb14', '#f5222d'
  ];

  const regionalOption = {
    color: chartColors,
    title: {
      text: totalCount.toLocaleString(),
      subtext: '总计',
      left: 'center',
      top: 'middle',
      textAlign: 'center',
      textStyle: {
        fontSize: 20,
        fontWeight: 'bold',
        color: '#1677ff',
        lineHeight: 22
      },
      subtextStyle: {
        fontSize: 11,
        color: '#8c8c8c',
        lineHeight: 14
      },
      itemGap: 4
    },
    tooltip: { trigger: 'item', formatter: '{b}: {c} 项 ({d}%)' },
    legend: { show: false },
    series: [
      {
        name: '分布区域',
        type: 'pie',
        radius: ['55%', '75%'],
        center: ['50%', '50%'],
        minAngle: 6,
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
          shadowBlur: 12,
          shadowOffsetX: 0,
          shadowOffsetY: 6,
          shadowColor: 'rgba(0, 0, 0, 0.18)'
        },
        label: { show: false },
        labelLine: { show: false },
        clockwise: true,
        animationType: 'expansion',
        animationDuration: 1500,
        animationEasing: 'cubicOut',
        data: chartData
      }
    ]
  };

  const generateReportText = () => {
    if (!selectedKeyword) return '';
    const rawData = regionalQuery.data || [];
    if (rawData.length === 0) return '暂无数据生成报告。';

    const totalCount = rawData.reduce((sum, item) => sum + item.count, 0);
    const topProvince = rawData[0];
    
    const growthItem = (growthQuery.data || []).find(item => item.keyword === selectedKeyword);
    const growthStr = growthItem 
      ? (growthItem.growth_rate >= 1000 ? '新晋爆发' : `环比暴增 +${growthItem.growth_rate}%`)
      : '稳步上升';

    let regionDetail = '';
    rawData.slice(0, 5).forEach((item, index) => {
      const pct = ((item.count / totalCount) * 100).toFixed(2);
      regionDetail += `* 第 ${index + 1} 名：**${item.province}**（${item.count} 项标准，占比 ${pct}%）\n`;
    });

    const otherData = rawData.slice(5);
    if (otherData.length > 0) {
      const otherSum = otherData.reduce((sum, item) => sum + item.count, 0);
      const otherPct = ((otherSum / totalCount) * 100).toFixed(2);
      regionDetail += `* 其他 ${otherData.length} 个地区：共计 **${otherSum} 项**，累计占比 ${otherPct}%\n`;
    }

    return `# 『${selectedKeyword}』产业研发趋势与地理集聚洞察报告

**分析周期**：近 ${days} 天全国企业标准数据监测
**数据来源**：EMIS 企业标准大数据监测中心

---

### 一、 研发风向与市场爆发力研判
1. **热度特征**：在近 ${days} 天的周期内，『**${selectedKeyword}**』被识别为重点前瞻性技术研发高频词。
2. **增速情况**：在全国企业申报统计中处于 **${growthStr}** 状态，预示着该细分品类正在经历密集的商业化备案与量产前置期。

### 二、 产业地理集群分布（Top 地区归因）
本期关联的 ${totalCount} 项企业标准中，起草企业的地理分布呈现出明显的集群特征：
${regionDetail}
其中，**${topProvince.province}** 在该赛道具备绝对主导优势（占比 ${((topProvince.count / totalCount) * 100).toFixed(2)}%），已形成稳固的核心产业集群。

### 三、 政府招商与企业投资决策建议
1. **地方政府招商建议**：
   - 鉴于 **${topProvince.province}** 的产业政策吸引力与供应链集中度，外省在布局『${selectedKeyword}』相关新产业时，可通过引入该地成熟溢出企业，加速实现本地的“强链补链”。
   - 若本地即为 **${topProvince.province}**，建议进一步出台专项孵化与扶持政策，全力打造国家级『${selectedKeyword}』先进实体制造业示范集群。
2. **企业研发与投研建议**：
   - 企业标准备案通常领先终端产品上市约 3 - 6 个月。目前『${selectedKeyword}』类标准的集中申报爆发，标志着大批新产品即将走向消费市场。
   - 建议投资机构、基金经理提前调研并布局相关产业链中具备高起草权、强研发储备优势的龙头上市与非上市企业。`;
  };

  const fallbackCopy = (text: string) => {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      const successful = document.execCommand('copy');
      if (successful) {
        message.success('报告已成功复制到剪贴板，可直接粘贴使用！');
      } else {
        message.error('复制失败，请手动选择文字复制。');
      }
    } catch (err) {
      message.error('复制失败，请手动选择文字复制。');
    }
    document.body.removeChild(textArea);
  };

  const handleCopyReport = () => {
    const text = generateReportText();
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
        .then(() => {
          message.success('报告已成功复制到剪贴板，可直接粘贴使用！');
        })
        .catch(() => {
          fallbackCopy(text);
        });
    } else {
      fallbackCopy(text);
    }
  };

  const reportButton = (
    <Button 
      type="primary" 
      size="small" 
      icon={<FileTextOutlined />} 
      onClick={() => setReportVisible(true)}
      disabled={!selectedKeyword || (regionalQuery.data || []).length === 0}
      style={{ borderRadius: 6 }}
    >
      生成分析报告
    </Button>
  );

  return (
    <div style={{ padding: 24, minHeight: '100vh', background: '#f0f2f5' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <RadarChartOutlined style={{ marginRight: 8, color: '#1677ff' }} />
          产业研发风向标洞察大屏
        </Title>
        <Select 
          value={days} 
          onChange={setDays}
          style={{ width: 160 }}
          options={[
            { value: 7, label: '近 7 天趋势' },
            { value: 30, label: '近 30 天趋势' },
            { value: 90, label: '近 90 天趋势' },
            { value: 365, label: '近 1 年趋势' },
          ]}
        />
      </div>

      <Row gutter={[24, 24]}>
        {/* 左侧：全局产业热词云 */}
        <Col xs={24} lg={14}>
          <Card 
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <span>
                  <FireOutlined style={{ color: '#fa8c16', marginRight: 4 }} /> 
                  全局产业热词风暴
                </span>
                {selectedKeyword && (
                  <Tag color="orange" style={{ margin: 0, borderRadius: 4, fontWeight: 'bold' }}>
                    当前分析：{selectedKeyword}
                  </Tag>
                )}
              </div>
            } 
            bordered={false} 
            style={{ borderRadius: 12, height: '100%', boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
          >
            {wordCloudQuery.isLoading ? (
              <div style={{ height: 500, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <Spin size="large" tip="正在进行全量企标 NLP 语义解析..." />
              </div>
            ) : (
              <ReactECharts 
                option={wordCloudOption} 
                style={{ height: 500 }} 
                onEvents={{ 'click': onWordClick }} 
                onChartReady={onChartReady}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={10}>
          <Row gutter={[0, 24]}>
            {/* 新兴赛道爆发环比增速榜 */}
            <Col span={24}>
              <Card 
                title={<><RiseOutlined style={{ color: '#f5222d' }} /> 新兴赛道爆发榜 (本期申报量与增速)</>} 
                bordered={false} 
                style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
              >
                {growthQuery.isLoading ? (
                  <div style={{ height: 200, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <Spin />
                  </div>
                ) : (
                  <ReactECharts option={growthOption} style={{ height: 220 }} />
                )}
              </Card>
            </Col>

            {/* 区域产业集群画像 */}
            <Col span={24}>
              <Card 
                title={
                  <>
                    <EnvironmentOutlined style={{ color: '#52c41a' }} /> 
                    『{selectedKeyword || '请选择热词'}』- 产业集群地理画像
                  </>
                } 
                extra={reportButton}
                bordered={false} 
                style={{ borderRadius: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.05)' }}
              >
                {regionalQuery.isLoading ? (
                  <div style={{ height: 200, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <Spin />
                  </div>
                ) : regionalQuery.data && regionalQuery.data.length > 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', height: 220, gap: '16px' }}>
                    <style>{`
                      .custom-scrollbar::-webkit-scrollbar {
                        width: 5px;
                      }
                      .custom-scrollbar::-webkit-scrollbar-track {
                        background: transparent;
                      }
                      .custom-scrollbar::-webkit-scrollbar-thumb {
                        background-color: #bfbfbf;
                        border-radius: 3px;
                      }
                      .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                        background-color: #8c8c8c;
                      }
                    `}</style>
                    <div style={{ flex: 1.2, height: '100%' }}>
                      <ReactECharts option={regionalOption} style={{ height: '100%', width: '100%' }} />
                    </div>
                    <div style={{ 
                      flex: 0.8, 
                      height: '100%', 
                      background: '#fafafa', 
                      borderRadius: 8, 
                      padding: '12px',
                      display: 'flex',
                      flexDirection: 'column',
                      minWidth: 0
                    }}>
                      <div style={{ 
                        fontSize: 12, 
                        fontWeight: 600, 
                        color: '#595959', 
                        marginBottom: 8,
                        flexShrink: 0
                      }}>
                        区域明细 ({sortedData.length})
                      </div>
                      <div style={{ 
                        flex: 1, 
                        overflowY: 'auto',
                        paddingRight: '4px'
                      }} className="custom-scrollbar">
                        {sortedData.map((item, index) => {
                          const percent = totalCount > 0 ? ((item.count / totalCount) * 100).toFixed(2) : '0.00';
                          const dotColor = listColors[index % listColors.length];
                          return (
                            <div 
                              key={item.province}
                              style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                fontSize: 11,
                                padding: '5px 0',
                                borderBottom: '1px solid #f0f0f0'
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
                                <span style={{ 
                                  width: 6, 
                                  height: 6, 
                                  borderRadius: '50%', 
                                  backgroundColor: dotColor,
                                  flexShrink: 0 
                                }} />
                                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {item.province}
                                </span>
                              </div>
                              <span style={{ 
                                color: '#595959', 
                                width: 40, 
                                textAlign: 'right', 
                                flexShrink: 0,
                                fontFamily: 'Consolas, Monaco, monospace' 
                              }}>
                                {item.count}
                              </span>
                              <span style={{ 
                                fontWeight: 'bold', 
                                color: '#1677ff', 
                                width: 65, 
                                textAlign: 'right', 
                                flexShrink: 0,
                                fontFamily: 'Consolas, Monaco, monospace' 
                              }}>
                                {percent}%
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div style={{ height: 220, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <Empty description={`暂无『${selectedKeyword}』的区域分布数据`} />
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </Col>
      </Row>

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <FileTextOutlined style={{ color: '#1677ff', marginRight: 8 }} />
            <span>智能生成产业分析报告</span>
          </div>
        }
        open={reportVisible}
        onCancel={() => setReportVisible(false)}
        footer={[
          <Button key="close" onClick={() => setReportVisible(false)}>
            关闭
          </Button>,
          <Button key="copy" type="primary" onClick={handleCopyReport}>
            复制报告内容
          </Button>,
        ]}
        width={720}
      >
        <div style={{ 
          padding: 16, 
          background: '#f8f9fa', 
          borderRadius: 8, 
          fontFamily: 'system-ui, -apple-system, sans-serif', 
          whiteSpace: 'pre-wrap', 
          fontSize: 13, 
          lineHeight: '1.6', 
          border: '1px solid #e8e8e8',
          maxHeight: '50vh',
          overflowY: 'auto'
        }}>
          {generateReportText()}
        </div>
      </Modal>
    </div>
  );
};

export default TrendDashboard;
