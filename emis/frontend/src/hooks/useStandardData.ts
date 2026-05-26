import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Standard, PaginatedResponse } from '@/types';
import { message } from 'antd';

export interface StandardSearchParams {
  page?: number;
  keyword?: string;
  company_id?: number;
  status?: string;
}

export const useStandardData = (params: StandardSearchParams) => {
  const queryClient = useQueryClient();

  // 获取标准列表
  const standardQuery = useQuery({
    queryKey: ['admin_standards', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Standard>>('/admin/standards/', { params });
      return data;
    },
  });

  // 创建/更新标准
  const saveMutation = useMutation({
    mutationFn: async (values: Partial<Standard>) => {
      if (values.id) {
        return apiClient.put(`/admin/standards/${values.id}/`, values);
      }
      return apiClient.post('/admin/standards/', values);
    },
    onSuccess: () => {
      message.success('操作成功');
      queryClient.invalidateQueries({ queryKey: ['admin_standards'] });
    },
  });

  // 物理删除标准
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/admin/standards/${id}/`),
    onSuccess: () => {
      message.success('标准删除成功');
      queryClient.invalidateQueries({ queryKey: ['admin_standards'] });
    },
  });

  return { standardQuery, saveMutation, deleteMutation };
};
