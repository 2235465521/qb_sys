import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Member, PaginatedResponse, OrganizationCategory } from '@/types';
import { message } from 'antd';

export const useMemberAdminData = (params: any) => {
  const queryClient = useQueryClient();

  // 获取后台会员列表
  const memberQuery = useQuery({
    queryKey: ['admin_members', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Member>>('/admin/members/', { params });
      return data;
    },
  });

  // 保存会员（新增/编辑）
  const saveMemberMutation = useMutation({
    mutationFn: async (values: Partial<Member>) => {
      if (values.id) {
        return apiClient.put(`/admin/members/${values.id}/`, values);
      }
      return apiClient.post('/admin/members/', values);
    },
    onSuccess: () => {
      message.success('会员信息已保存');
      queryClient.invalidateQueries({ queryKey: ['admin_members'] });
    },
  });

  // 删除会员
  const deleteMemberMutation = useMutation({
    mutationFn: async (id: number) => {
      return apiClient.delete(`/admin/members/${id}/`);
    },
    onSuccess: () => {
      message.success('会员已彻底删除');
      queryClient.invalidateQueries({ queryKey: ['admin_members'] });
    },
  });

  // 获取自定义分类列表
  const categoryQuery = useQuery<OrganizationCategory[]>({
    queryKey: ['member_categories'],
    queryFn: async () => {
      const { data } = await apiClient.get<OrganizationCategory[] | { results: OrganizationCategory[] }>('/client/members/categories/');
      return Array.isArray(data) ? data : (data?.results || []);
    },
  });




  // 创建分类
  const createCategoryMutation = useMutation({
    mutationFn: async (values: { name: string, code: string }) => {
      const { data } = await apiClient.post<OrganizationCategory>('/client/members/categories/', values);
      return data;
    },
    onSuccess: () => {
      message.success('自定义分类模块已创建');
      queryClient.invalidateQueries({ queryKey: ['member_categories'] });
    },
  });

  // 删除分类
  const deleteCategoryMutation = useMutation({
    mutationFn: async (id: number) => {
      return apiClient.delete(`/client/members/categories/${id}/`);
    },
    onSuccess: () => {
      message.success('分类已删除');
      queryClient.invalidateQueries({ queryKey: ['member_categories'] });
    },
  });

  return { 
    memberQuery, 
    saveMemberMutation, 
    deleteMemberMutation,
    categoryQuery,
    createCategoryMutation,
    deleteCategoryMutation
  };
};
