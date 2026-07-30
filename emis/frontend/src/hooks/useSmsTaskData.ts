import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { SmsTask, SmsTemplate, PaginatedResponse } from '@/types';
import { message } from 'antd';

export const useSmsTaskData = (params?: { page: number }) => {
  const queryClient = useQueryClient();

  // 获取短信任务列表（支持分页）
  const taskQuery = useQuery({
    queryKey: ['sms_tasks', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<SmsTask>>('/admin/notifications/tasks/', {
        params,
      });
      return data;
    },
  });

  const activeTemplatesQuery = useQuery<SmsTemplate[]>({
    queryKey: ['active_sms_templates'],
    queryFn: async () => {
      const { data } = await apiClient.get<SmsTemplate[] | { results: SmsTemplate[] }>('/admin/notifications/templates/');
      const list = Array.isArray(data) ? data : (data?.results || []);
      return list.filter((t: SmsTemplate) => t.is_active);
    },
  });




  // 创建并提交群发任务
  const createTaskMutation = useMutation({
    mutationFn: async (values: {
      template: number;
      target_group: string;
      target_company?: string;
      scheduled_time?: string | null;
    }) => {
      // 容错处理：清除空串
      const payload = {
        ...values,
        target_company: values.target_group === 'specific_company' ? values.target_company : '',
      };
      const { data } = await apiClient.post<SmsTask>('/admin/notifications/tasks/', payload);
      return data;
    },
    onSuccess: () => {
      message.success('短信群发任务已提交');
      queryClient.invalidateQueries({ queryKey: ['sms_tasks'] });
    },
    onError: (error: Error) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const err = error as any;
      const errorMsg = err.response?.data?.detail || error.message || '提交任务失败，请检查参数';
      message.error(errorMsg);
    },
  });

  return {
    taskQuery,
    activeTemplatesQuery,
    createTaskMutation,
  };
};
