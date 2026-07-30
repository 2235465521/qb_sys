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
  const useCompanyFederatedStandards = (companyId?: number, scope: 'expanded' | 'core' = 'expanded') => useQuery({
    queryKey: ['company_federated_standards', companyId, scope],
    queryFn: async () => {
      if (!companyId) return {
        standards: [],
        total_standards: 0,
        type_breakdown: { 'GB/T': 0, 'TB': 0, 'DB': 0, 'industry': 0, 'other': 0 },
        credit_code: '',
        scope: scope,
        matched_units: []
      };
      const { data } = await apiClient.get<{
        standards: Standard[],
        total_standards: number,
        type_breakdown?: Record<string, number>,
        credit_code?: string,
        scope?: string,
        matched_units?: string[]
      }>(`/client/search/companies/${companyId}/federated_standards/`, { params: { scope } });
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

  // 导出指定企业的标准资产目录为 Excel
  const exportCompanyStandardsExcel = async (companyId: number, scope: 'expanded' | 'core' = 'expanded', selectedIds?: any[]) => {
    const response = await apiClient.post(
      `/client/search/companies/${companyId}/export-standards/`,
      { scope, selected_ids: selectedIds || [] },
      { responseType: 'blob' }
    );

    if (response.data && response.data.type === 'application/json') {
      const text = await response.data.text();
      let errDetail = '导出文件失败';
      try {
        const errObj = JSON.parse(text);
        errDetail = errObj.detail || errObj.message || errDetail;
      } catch (e) {}
      throw new Error(errDetail);
    }

    let filename = `企业标准资产清单_${scope}.xlsx`;
    const disposition = response.headers['content-disposition'];
    if (disposition && disposition.includes('filename*=')) {
      const match = disposition.match(/filename\*=UTF-8''(.+)/);
      if (match && match[1]) {
        filename = decodeURIComponent(match[1]);
      }
    }

    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  };


  return { useCompanySearch, useCompanyStandards, useCompanyFederatedStandards, zipMutation, checkZipStatus, exportCompanyStandardsExcel };
};

