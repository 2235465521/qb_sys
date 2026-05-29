import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { message } from 'antd';

export interface Attachment {
  id: number;
  file: string;
  filename: string;
  size: number;
  file_url: string;
  created_at: string;
}

export interface FollowUp {
  id: number;
  lead: number;
  content: string;
  created_at: string;
  creator: number;
  creator_name: string;
}

export interface Lead {
  id?: number;
  source: 'wechat' | 'phone' | 'visit' | 'other';
  source_display?: string;
  req_type: 'data_correction' | 'business_cooperation' | 'general_inquiry';
  req_type_display?: string;
  status: 'pending' | 'following' | 'solved' | 'closed';
  status_display?: string;
  assignee: number | null;
  assignee_name?: string;
  enterprise: number | null;
  enterprise_name?: string;
  enterprise_credit_code?: string;
  contact_name: string;
  contact_phone: string;
  contact_wechat: string;
  followups?: FollowUp[];
  attachments?: Attachment[];
  created_at?: string;
  updated_at?: string;
}

// 保持向前兼容的别名
export type CompanyLead = Lead;

export interface LeadListParams {
  page?: number;
  keyword?: string;
  status?: string;
  source?: string;
}

export const useCompanyLeads = () => {
  const queryClient = useQueryClient();

  // 1. Client Lead Creation Mutation (POST to /client/search/leads/)
  const createLeadMutation = useMutation({
    mutationFn: async (leadData: Partial<Lead>) => {
      const { data } = await apiClient.post<Lead>('/client/search/leads/', leadData);
      return data;
    },
    onSuccess: () => {
      message.success('意向线索提交成功！运营团队将第一时间跟进处理。');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      console.error(err);
      message.error(err.response?.data?.detail || '建档失败，请检查填写内容！');
    }
  });

  // 2. Admin Leads List Query (GET from /admin/companies/leads/)
  const useAdminLeads = (params: LeadListParams) => {
    return useQuery({
      queryKey: ['admin_leads', params],
      queryFn: async () => {
        const { data } = await apiClient.get<{ results: Lead[]; count: number }>('/admin/companies/leads/', {
          params
        });
        return data;
      }
    });
  };

  // 3. Admin Lead Creation Mutation (POST to /admin/companies/leads/)
  const createAdminLeadMutation = useMutation({
    mutationFn: async (leadData: FormData) => {
      const { data } = await apiClient.post<Lead>('/admin/companies/leads/', leadData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return data;
    },
    onSuccess: () => {
      message.success('意向线索新建成功！');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail || '新建线索失败，请重试！');
    }
  });

  // 4. Admin Lead Update Mutation (PUT/PATCH to /admin/companies/leads/:id/)
  const updateLeadMutation = useMutation({
    mutationFn: async ({ id, ...leadData }: { id: number } & Partial<Lead>) => {
      const { data } = await apiClient.patch<Lead>(`/admin/companies/leads/${id}/`, leadData);
      return data;
    },
    onSuccess: () => {
      message.success('线索跟进状态更新成功！');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail || '更新失败，请重试！');
    }
  });

  // 5. Admin Lead Delete Mutation (DELETE /admin/companies/leads/:id/)
  const deleteLeadMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/admin/companies/leads/${id}/`);
    },
    onSuccess: () => {
      message.success('销售线索删除成功。');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      console.error(err);
      message.error('删除失败，请重试！');
    }
  });

  // 6. Admin Add FollowUp & Upload Attachments (POST to /admin/companies/leads/:id/followup/)
  const addFollowUpMutation = useMutation({
    mutationFn: async ({ leadId, formData }: { leadId: number; formData: FormData }) => {
      const { data } = await apiClient.post<Lead>(`/admin/companies/leads/${leadId}/followup/`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      return data;
    },
    onSuccess: () => {
      message.success('跟进记录与附件提交成功！');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      message.error(err.response?.data?.detail || '跟进提交失败，请重试！');
    }
  });

  // 7. Admin Delete Lead Attachment (POST to /admin/companies/leads/:id/delete_attachment/)
  const deleteAttachmentMutation = useMutation({
    mutationFn: async ({ leadId, attachmentId }: { leadId: number; attachmentId: number }) => {
      const { data } = await apiClient.post<Lead>(`/admin/companies/leads/${leadId}/delete_attachment/`, {
        attachment_id: attachmentId
      });
      return data;
    },
    onSuccess: () => {
      message.success('附件已成功删除。');
      queryClient.invalidateQueries({ queryKey: ['admin_leads'] });
    },
    onError: (err: any) => {
      message.error(err.response?.data?.error || '删除附件失败，请重试！');
    }
  });

  return {
    createLeadMutation,
    useAdminLeads,
    createAdminLeadMutation,
    updateLeadMutation,
    deleteLeadMutation,
    addFollowUpMutation,
    deleteAttachmentMutation
  };
};

