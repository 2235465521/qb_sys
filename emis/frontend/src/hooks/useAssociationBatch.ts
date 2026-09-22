import { useState, useCallback } from 'react';
import { message } from 'antd';
import apiClient from '@/api/client';
import type { AssociationBatchResult, AssociationBatchItem } from '@/types';

export const useAssociationBatch = () => {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<AssociationBatchResult | null>(null);
  const [selectedNames, setSelectedNames] = useState<string[]>([]);
  const [activeDetailItem, setActiveDetailItem] = useState<AssociationBatchItem | null>(null);

  // 1. 通过上传 Excel 文件批量查询
  const queryByFile = useCallback(async (file: File) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const { data } = await apiClient.post<AssociationBatchResult>(
        '/client/search/associations/batch-query/',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      setResult(data);
      // 默认全选所有解析出的社团
      setSelectedNames(data.items.map((it) => it.input_name));
      message.success(
        `成功识别 ${data.total_input} 家社团组织，匹配到 ${data.total_standards_count} 项标准资产！`
      );
      return data;
    } catch (err: any) {
      const errMsg = err.response?.data?.error || err.message || '解析 Excel 失败，请检查文件格式';
      message.error(errMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. 通过粘贴社团名称列表批量查询
  const queryByNames = useCallback(async (names: string[]) => {
    if (!names || names.length === 0) {
      message.warning('请输入至少一个有效的社团/协会名称');
      return;
    }
    setLoading(true);
    try {
      const { data } = await apiClient.post<AssociationBatchResult>(
        '/client/search/associations/batch-query/',
        { names }
      );

      setResult(data);
      setSelectedNames(data.items.map((it) => it.input_name));
      message.success(
        `成功查询 ${data.total_input} 家社团组织，匹配到 ${data.total_standards_count} 项标准资产！`
      );
      return data;
    } catch (err: any) {
      const errMsg = err.response?.data?.error || err.message || '批量查询失败，请稍后重试';
      message.error(errMsg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // 3. 批量合并导出为一张 Excel
  const exportMergedExcel = useCallback(async (customNames?: string[]) => {
    const targetNames = customNames || selectedNames;
    if (!targetNames || targetNames.length === 0) {
      message.warning('请至少勾选一家需要导出的社团组织');
      return;
    }

    setExporting(true);
    try {
      const response = await apiClient.post(
        '/client/search/associations/batch-export/',
        { names: targetNames },
        { responseType: 'blob' }
      );

      let filename = `社团协会标准资产汇总及明细目录_${Date.now()}.xlsx`;
      const disposition = response.headers['content-disposition'];
      if (disposition && disposition.includes('filename*=')) {
        const match = disposition.match(/filename\*=UTF-8''(.+)/);
        if (match && match[1]) {
          filename = decodeURIComponent(match[1]);
        }
      }

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      message.success(`已成功导出 ${targetNames.length} 家社团的合并标准目录大表！`);
    } catch (err: any) {
      console.error('Export error:', err);
      message.error('导出合并 Excel 文件失败，请稍后重试');
    } finally {
      setExporting(false);
    }
  }, [selectedNames]);

  const reset = useCallback(() => {
    setResult(null);
    setSelectedNames([]);
    setActiveDetailItem(null);
  }, []);

  return {
    loading,
    exporting,
    result,
    selectedNames,
    setSelectedNames,
    activeDetailItem,
    setActiveDetailItem,
    queryByFile,
    queryByNames,
    exportMergedExcel,
    reset,
  };
};
