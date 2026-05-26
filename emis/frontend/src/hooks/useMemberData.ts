import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Member, SmsTask, PaginatedResponse, OrganizationCategory } from '@/types';
import { message } from 'antd';

export const useMemberData = (params: any) => {
  const queryClient = useQueryClient();

  // 获取会员列表
  const memberQuery = useQuery({
    queryKey: ['client_members', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Member>>('/client/members/', { params });
      return data;
    },
  });

  // 保存会员（采集）
  const saveMemberMutation = useMutation({
    mutationFn: async (values: Partial<Member>) => {
      if (values.id) {
        return apiClient.put(`/client/members/${values.id}/`, values);
      }
      return apiClient.post('/client/members/', values);
    },
    onSuccess: () => {
      message.success('会员信息已保存');
      queryClient.invalidateQueries({ queryKey: ['client_members'] });
    },
  });

  // 提交短信群发任务
  const smsTaskMutation = useMutation({
    mutationFn: async (values: { template: number, target_group: string, target_company?: string }) => {
      const { data } = await apiClient.post<SmsTask>('/admin/notifications/tasks/', values);
      return data;
    },
    onSuccess: () => {
      message.success('短信群发任务已提交至后台队列');
    },
  });

  // 获取自定义分类列表
  const categoryQuery = useQuery({
    queryKey: ['member_categories'],
    queryFn: async () => {
      const { data } = await apiClient.get<OrganizationCategory[]>('/client/members/categories/');
      return data;
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
    smsTaskMutation,
    categoryQuery,
    createCategoryMutation,
    deleteCategoryMutation
  };
};
