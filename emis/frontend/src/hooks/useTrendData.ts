import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';

export interface TrendWord {
  name: string;
  value: number;
}

export interface GrowthRanking {
  keyword: string;
  growth_rate: number;
  current_count: number;
}

export interface RegionalDist {
  province: string;
  count: number;
}

export const useTrendData = (days: number = 30, selectedKeyword: string = '') => {
  const wordCloudQuery = useQuery({
    queryKey: ['trend_word_cloud', days],
    queryFn: async () => {
      const { data } = await apiClient.get<TrendWord[]>('/client/analysis/trends/word-cloud/', {
        params: { days, limit: 100 }
      });
      return data;
    },
    staleTime: 1000 * 60 * 30, // Cache for 30 minutes
  });

  const growthQuery = useQuery({
    queryKey: ['trend_growth', days],
    queryFn: async () => {
      const { data } = await apiClient.get<GrowthRanking[]>('/client/analysis/trends/growth-ranking/', {
        params: { days, limit: 10 }
      });
      return data;
    },
    staleTime: 1000 * 60 * 30,
  });

  const regionalQuery = useQuery({
    queryKey: ['trend_regional', selectedKeyword, days],
    queryFn: async () => {
      if (!selectedKeyword) return [];
      const { data } = await apiClient.get<RegionalDist[]>('/client/analysis/trends/regional-dist/', {
        params: { keyword: selectedKeyword, days }
      });
      return data;
    },
    enabled: !!selectedKeyword,
    staleTime: 1000 * 60 * 30,
  });

  return {
    wordCloudQuery,
    growthQuery,
    regionalQuery
  };
};
