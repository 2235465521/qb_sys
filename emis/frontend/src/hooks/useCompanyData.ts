import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Company, CompanySearchParams, PaginatedResponse } from '@/types';
import { message } from 'antd';

export const useCompanyData = (params: CompanySearchParams) => {
  const queryClient = useQueryClient();

  // 获取企业列表
  const companyQuery = useQuery({
    queryKey: ['admin_companies', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Company>>('/admin/companies/', { params });
      return data;
    },
  });

  // 创建/更新企业
  const saveMutation = useMutation({
    mutationFn: async (values: Partial<Company>) => {
      if (values.id) {
        return apiClient.patch(`/admin/companies/${values.id}/`, values);
      }
      return apiClient.post('/admin/companies/', values);
    },
    onSuccess: () => {
      message.success('操作成功');
      queryClient.invalidateQueries({ queryKey: ['admin_companies'] });
      companyQuery.refetch();
    },
    onError: (error: any) => {
      const data = error.response?.data;
      let errorMsg = '保存失败，请检查输入项';
      if (typeof data === 'string') {
        errorMsg = data;
      } else if (data && typeof data === 'object') {
        const firstKey = Object.keys(data)[0];
        const val = data[firstKey];
        if (Array.isArray(val) && val.length > 0) {
          errorMsg = `${val[0]}`;
        } else if (typeof val === 'string') {
          errorMsg = val;
        } else if (data.error) {
          errorMsg = data.error;
        } else if (data.detail) {
          errorMsg = data.detail;
        }
      }
      message.error(errorMsg);
    },
  });

  // 软删除企业
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/admin/companies/${id}/`),
    onSuccess: () => {
      message.success('企业已删除');
      queryClient.invalidateQueries({ queryKey: ['admin_companies'] });
      companyQuery.refetch();
    },
  });

  return { companyQuery, saveMutation, deleteMutation };
};
