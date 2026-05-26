import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { SmsTemplate } from '@/types';
import { message } from 'antd';

export const useSmsData = () => {
  const queryClient = useQueryClient();

  // 获取模板列表
  const templateQuery = useQuery({
    queryKey: ['sms_templates'],
    queryFn: async () => {
      const { data } = await apiClient.get<SmsTemplate[]>('/admin/notifications/templates/');
      return data;
    },
  });

  // 保存模板（新建/更新）
  const saveMutation = useMutation({
    mutationFn: async (values: Partial<SmsTemplate>) => {
      if (values.id) {
        return apiClient.put(`/admin/notifications/templates/${values.id}/`, values);
      }
      return apiClient.post('/admin/notifications/templates/', values);
    },
    onSuccess: () => {
      message.success('模板保存成功');
      queryClient.invalidateQueries({ queryKey: ['sms_templates'] });
    },
  });

  // 删除模板
  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/admin/notifications/templates/${id}/`),
    onSuccess: () => {
      message.success('模板已删除');
      queryClient.invalidateQueries({ queryKey: ['sms_templates'] });
    },
  });

  return { templateQuery, saveMutation, deleteMutation };
};
