import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { message } from 'antd';

export interface CitationRank {
  id: number;
  standard_no: string;
  title: string;
  citation_count: number;
}

export const useAnalysisData = () => {
  const queryClient = useQueryClient();

  // 获取国标引用排名
  const rankQuery = useQuery({
    queryKey: ['citation_ranking'],
    queryFn: async () => {
      const { data } = await apiClient.get<{ results: CitationRank[] }>('/client/analysis/citation-rank/', {
        params: { limit: 100 }
      });
      return data.results;
    },
  });

  // 上传并解析引用 Excel（支持批量文件上传）
  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const results = [];
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
          const { data } = await apiClient.post('/client/analysis/upload/', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          results.push({
            fileName: file.name,
            success: true,
            parsed_standards: data.parsed_standards || 0,
            citations_added: data.citations_added || 0,
            errors: data.errors || []
          });
        } catch (err: any) {
          results.push({
            fileName: file.name,
            success: false,
            parsed_standards: 0,
            citations_added: 0,
            errors: [err.response?.data?.error || err.message || '上传或请求出错']
          });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      let totalParsed = 0;
      let totalAdded = 0;
      let totalErrorsCount = 0;
      
      results.forEach(res => {
        totalParsed += res.parsed_standards;
        totalAdded += res.citations_added;
        totalErrorsCount += res.errors.length;
      });
      
      if (totalErrorsCount > 0) {
        message.warning(`批量解析完成！成功解析 ${totalParsed} 个企标，更新 ${totalAdded} 条引用。共发现 ${totalErrorsCount} 个错误。`);
      } else {
        message.success(`成功批量解析 ${results.length} 个 Excel 文件！共解析 ${totalParsed} 个企标，更新了 ${totalAdded} 条引用。`);
      }
      // 刷新排名
      queryClient.invalidateQueries({ queryKey: ['citation_ranking'] });
    },
  });

  return { rankQuery, uploadMutation };
};
