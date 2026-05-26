import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Province, City, District } from '@/types';

export const useDictData = () => {
  // 获取省份
  const provinceQuery = useQuery({
    queryKey: ['dict_provinces'],
    queryFn: async () => {
      const { data } = await apiClient.get<Province[]>('/admin/dict/provinces/');
      return data;
    },
    staleTime: Infinity, // 字典数据基本不变
  });

  // 获取城市
  const useCityQuery = (provinceId?: number) => useQuery({
    queryKey: ['dict_cities', provinceId],
    queryFn: async () => {
      if (!provinceId) return [];
      const { data } = await apiClient.get<City[]>('/admin/dict/cities/', {
        params: { province_id: provinceId }
      });
      return data;
    },
    enabled: !!provinceId,
    staleTime: Infinity,
  });

  // 获取区县
  const useDistrictQuery = (cityId?: number) => useQuery({
    queryKey: ['dict_districts', cityId],
    queryFn: async () => {
      if (!cityId) return [];
      const { data } = await apiClient.get<District[]>('/admin/dict/districts/', {
        params: { city_id: cityId }
      });
      return data;
    },
    enabled: !!cityId,
    staleTime: Infinity,
  });

  return { provinceQuery, useCityQuery, useDistrictQuery };
};
