import { useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Company, CompanySearchParams, Standard, PaginatedResponse } from '@/types';

export const useSearchData = () => {
  // 搜索企业（支持 LBS）
  const useCompanySearch = (params: CompanySearchParams) => useQuery({
    queryKey: ['client_company_search', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Company>>('/client/search/companies/', { params });
      return data;
    },
  });

  // 获取企业名下的企标
  const useCompanyStandards = (companyId?: number) => useQuery({
    queryKey: ['company_standards', companyId],
    queryFn: async () => {
      if (!companyId) return [];
      const { data } = await apiClient.get<PaginatedResponse<Standard> | Standard[]>(`/client/search/companies/${companyId}/standards/`);
      return Array.isArray(data) ? data : (data.results || []);
    },
    enabled: !!companyId,
  });

  // 获取企业联邦查询的标准（国标、行标等）
  const useCompanyFederatedStandards = (companyId?: number) => useQuery({
    queryKey: ['company_federated_standards', companyId],
    queryFn: async () => {
      if (!companyId) return { standards: [], total_standards: 0 };
      const { data } = await apiClient.get<{standards: Standard[], total_standards: number}>(`/client/search/companies/${companyId}/federated_standards/`);
      return data;
    },
    enabled: !!companyId,
  });

  // 请求 ZIP 打包
  const zipMutation = useMutation({
    mutationFn: async (standardIds: number[]) => {
      const { data } = await apiClient.post<{ token: string, status: string }>('/client/standards/pack/', {
        standard_ids: standardIds
      });
      return data;
    },
  });

  // 检查 ZIP 状态
  const checkZipStatus = async (token: string) => {
    const { data } = await apiClient.get<{
      status: 'pending' | 'running' | 'done' | 'failed',
      download_url?: string
    }>(`/client/standards/pack/${token}/status/`);
    return data;
  };

  return { useCompanySearch, useCompanyStandards, useCompanyFederatedStandards, zipMutation, checkZipStatus };
};
