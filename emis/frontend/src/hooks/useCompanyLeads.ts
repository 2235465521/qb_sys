import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/client';
import { message } from 'antd';

export interface CompanyLead {
  id?: number;
  company: number;
  company_name?: string;
  company_credit_code?: string;
  source: 'wechat_mp' | 'wechat_video' | 'referral' | 'active_inquiry' | 'other';
  source_display?: string;
  contact_name: string;
  contact_phone: string;
  contact_wechat: string;
  status: 'pending' | 'contacted' | 'interested' | 'vip_signed' | 'failed';
  status_display?: string;
  memo: string;
  created_at?: string;
  updated_at?: string;
}

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
    mutationFn: async (leadData: Partial<CompanyLead>) => {
      const { data } = await apiClient.post<CompanyLead>('/client/search/leads/', leadData);
      return data;
    },
    onSuccess: () => {
      message.success('意向线索建档成功！运营团队将第一时间跟进处理。');
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
        const { data } = await apiClient.get<{ results: CompanyLead[]; count: number }>('/admin/companies/leads/', {
          params
        });
        return data;
      }
    });
  };

  // 3. Admin Lead Update Mutation (PUT to /admin/companies/leads/:id/)
  const updateLeadMutation = useMutation({
    mutationFn: async ({ id, ...leadData }: { id: number } & Partial<CompanyLead>) => {
      const { data } = await apiClient.put<CompanyLead>(`/admin/companies/leads/${id}/`, leadData);
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

  // 4. Admin Lead Delete Mutation (DELETE /admin/companies/leads/:id/)
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

  return {
    createLeadMutation,
    useAdminLeads,
    updateLeadMutation,
    deleteLeadMutation
  };
};
