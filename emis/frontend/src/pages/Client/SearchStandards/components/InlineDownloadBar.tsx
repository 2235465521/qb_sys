import React, { useState, useRef, useCallback } from 'react';
import { Select, InputNumber, Button, Space, message, Typography, Tooltip } from 'antd';
import { DownloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import apiClient from '@/api/client';
import { useTaskContext } from '@/store/TaskContext';

const { Text } = Typography;

interface InlineDownloadBarProps {
  /** 当前检索条件返回的总记录数 */
  totalCount: number;
  /** 当前搜索页面所有过滤参数（和 SearchForm 提交给父组件的 params 一致） */
  filters: Record<string, any>;
}

const InlineDownloadBar: React.FC<InlineDownloadBarProps> = ({ totalCount, filters }) => {
  const [strategy, setStrategy] = useState<'random' | 'latest'>('random');
  const [count, setCount] = useState<number>(100);
  const [loading, setLoading] = useState(false);
  const isRequesting = useRef(false);       // 防并发锁
  const { dispatchTask } = useTaskContext();

  // 去掉 filters 中的 page 字段，避免传给后端
  const buildFilters = useCallback(() => {
    const { page, ...rest } = filters as any;
    return rest;
  }, [filters]);

  const handleDownload = useCallback(async () => {
    // 防止重复点击
    if (isRequesting.current) return;
    if (totalCount === 0) {
      message.warning('当前检索结果为空，无法下载');
      return;
    }

    isRequesting.current = true;
    setLoading(true);
    const hide = message.loading('正在为您打包提取文件，请稍候...', 0);

    try {
      const payload = {
        strategy,
        count: Math.min(count, totalCount),
        filters: buildFilters(),
      };

      const { data } = await apiClient.post<{
        parts: { token: string; count: number; status: string }[];
        total_sampled: number;
        split_count: number;
      }>('/client/standards/sampled-pack/', payload);

      hide();

      const { parts, total_sampled, split_count } = data;

      if (split_count === 1) {
        // 单个分片，直接轮询下载
        const { token, count: partCount } = parts[0];
        message.success(
          `已锁定 ${total_sampled} 个企标，打包任务已提交，您可继续浏览...`
        );
        dispatchTask(token, `抽样打包下载 (${total_sampled}个)`, false, '/client/standards/sampled-pack/', payload);
      } else {
        // 多分片，依次弹出
        message.success(
          `文件较大，已自动拆分为 ${split_count} 个压缩包（共 ${total_sampled} 个企标），将依次为您提交打包任务...`
        );
        parts.forEach((part, idx) => {
          dispatchTask(
            part.token,
            `抽样打包下载 第${idx + 1}/${split_count}包 (${part.count}个)`,
            false,
            '/client/standards/sampled-pack/',
            payload
          );
        });
      }
    } catch (err: any) {
      hide();
      const errMsg = err.response?.data?.error || '打包请求失败，请稍后重试';
      message.error(errMsg);
    } finally {
      setLoading(false);
      isRequesting.current = false;
    }
  }, [strategy, count, totalCount, buildFilters, dispatchTask]);

  const disabled = totalCount === 0;

  return (
    <Space
      size={8}
      align="center"
      style={{ flexWrap: 'nowrap' }}
    >
      {/* 抽样策略 */}
      <Select
        value={strategy}
        onChange={(v) => setStrategy(v)}
        disabled={disabled || loading}
        style={{ width: 148 }}
        options={[
          { value: 'random', label: '随机抽样' },
          { value: 'latest', label: '按最新发布' },
        ]}
        size="middle"
      />

      {/* 抽样数量 */}
      <InputNumber
        min={1}
        max={Math.max(totalCount, 1)}
        value={count}
        onChange={(v) => setCount(v ?? 100)}
        disabled={disabled || loading}
        style={{ width: 90 }}
        size="middle"
        placeholder="数量"
      />

      {/* 提示说明 */}
      <Tooltip
        title={
          totalCount > 0
            ? `将从当前 ${totalCount} 条结果中按所选策略抽取，超过 1 GB 自动拆分多包`
            : '请先执行检索后再使用抽样下载'
        }
      >
        <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help', fontSize: 14 }} />
      </Tooltip>

      {/* 打包下载按钮 */}
      <Button
        type="primary"
        icon={<DownloadOutlined />}
        loading={loading}
        disabled={disabled}
        onClick={handleDownload}
        style={{
          borderRadius: 8,
          background: disabled
            ? undefined
            : 'linear-gradient(135deg, #00acc1 0%, #00838f 100%)',
          borderColor: disabled ? undefined : '#00acc1',
          fontWeight: 'bold',
          boxShadow: disabled ? undefined : '0 4px 12px rgba(0, 131, 143, 0.25)',
          transition: 'all 0.25s ease',
        }}
      >
        打包下载
      </Button>
    </Space>
  );
};

export default InlineDownloadBar;
