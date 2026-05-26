import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Standard, PaginatedResponse } from '@/types';

export interface ClientStandardSearchParams {
  page?: number;
  keyword?: string;
  type?: string;
}

export const useClientStandardSearch = (params: ClientStandardSearchParams) => {
  return useQuery({
    queryKey: ['client_standards_search', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Standard>>('/client/standards/', {
        params: {
          ...params,
          type: 'enterprise', // Focus explicitly on corporate standards as requested ("搜索企标")
        }
      });
      return data;
    },
  });
};
