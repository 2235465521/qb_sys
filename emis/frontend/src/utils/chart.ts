import type { EChartsOption } from 'echarts';

interface PieDataItem {
  name: string;
  value: number;
}

/**
 * 生产极具现代感、大厂数据大屏风格环形图（Donut Chart）配置项的工厂函数。
 * 
 * 特色：
 * 1. 扇叶接力开花动画（animationType: 'expansion' + cubicInOut + animationDelay 顺次延时入场）
 * 2. 伪 3D 浮雕投影质感与圆润圆角（shadowBlur + shadowColor + shadowOffset + borderRadius）
 * 3. 极佳排版与防重叠（通过 minAngle 与 roseType 针对极端数据进行优雅适配）
 */
export const makeAnalyticsPieChartPair = (
  data: PieDataItem[],
  titleText: string = '数据分析',
  subText: string = '占比明细'
): EChartsOption => {
  const total = data.reduce((sum, item) => sum + item.value, 0);

  // 炫酷渐变色彩集 (现代 SaaS / 数据大屏大厂配色系统)
  const chartColors = [
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#69b1ff' }, { offset: 1, color: '#1677ff' }] // 3D 科技蓝
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#95de64' }, { offset: 1, color: '#52c41a' }] // 3D 生态绿
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ffd591' }, { offset: 1, color: '#fa8c16' }] // 3D 活力黄橙
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ff9c6e' }, { offset: 1, color: '#fa541c' }] // 3D 珊瑚红橙
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#ff85c0' }, { offset: 1, color: '#eb2f96' }] // 3D 绚丽粉色
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#b37feb' }, { offset: 1, color: '#722ed1' }] // 3D 梦幻紫
    },
    {
      type: 'linear', x: 0, y: 0, x2: 1, y2: 1,
      colorStops: [{ offset: 0, color: '#5cdbd3' }, { offset: 1, color: '#13c2c2' }] // 3D 翡翠青
    }
  ];

  return {
    animation: true,
    color: chartColors as any,
    title: {
      text: total.toLocaleString(),
      subtext: subText,
      left: 'center',
      top: 'middle',
      textAlign: 'center',
      textStyle: {
        fontSize: 22,
        fontWeight: 'bold',
        color: '#1f2937', // Tailwind Slate-800 风格
        lineHeight: 26
      },
      subtextStyle: {
        fontSize: 12,
        color: '#6b7280', // Tailwind Slate-500 风格
        lineHeight: 16
      },
      itemGap: 4
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: '#e5e7eb',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: {
        color: '#1f2937',
        fontSize: 13,
        fontFamily: 'system-ui, sans-serif'
      },
      extraCssText: 'box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); border-radius: 8px;',
      formatter: '{b}: <span style="font-weight: bold; color:#1677ff;">{c}</span> 项 ({d}%)'
    },
    legend: {
      show: false // 数据与视图分离：交由外层封装好的 React PieRankList 表格显示列表
    },
    series: [
      {
        name: titleText,
        type: 'pie',
        radius: ['53%', '73%'],
        center: ['50%', '50%'],
        // 限制小扇形最小角度，防止在多数据、低占比极端情况下发生重叠重合
        minAngle: 8,
        avoidLabelOverlap: true,
        // 数据量很多时（例如多于12个）启用玫瑰图排版，优化环形比例的利用率与重叠
        roseType: data.length > 12 ? 'radius' : undefined,
        itemStyle: {
          borderRadius: 8,       // 优美的气泡质感圆角
          borderColor: '#ffffff', // 边界白色勾缝间隙
          borderWidth: 2,
          // 悬浮 3D 呼吸投影效果
          shadowBlur: 16,
          shadowColor: 'rgba(0, 0, 0, 0.13)',
          shadowOffsetX: 2,
          shadowOffsetY: 5
        },
        label: {
          show: false // 完全配合外层表格展示，饼图内部标签静默不显，保证大屏纯净高雅
        },
        labelLine: {
          show: false
        },
        clockwise: true,
        // 动效核心配置：扇形延迟开花展开动画
        animationType: 'expansion',    // 扇形入场动画
        animationDuration: 2500,       // 基础时长 2.5 秒，慢速美观
        animationEasing: 'cubicInOut', // 平滑缓动
        animationDelay: (idx: number) => idx * 200, // 接力顺次展开
        data: data
      }
    ]
  };
};
