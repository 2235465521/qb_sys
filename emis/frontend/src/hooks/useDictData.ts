import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';
import type { Province, City, District, CompanyCategory } from '@/types';

export const useDictData = () => {
  // 获取省份
  const provinceQuery = useQuery<Province[]>({
    queryKey: ['dict_provinces'],
    queryFn: async () => {
      const { data } = await apiClient.get<Province[] | { results: Province[] }>('/admin/dict/provinces/');
      return Array.isArray(data) ? data : (data?.results || []);
    },
    staleTime: Infinity, // 字典数据基本不变
  });

  // 获取城市
  const useCityQuery = (provinceId?: number) => useQuery<City[]>({
    queryKey: ['dict_cities', provinceId],
    queryFn: async () => {
      if (!provinceId) return [];
      const { data } = await apiClient.get<City[] | { results: City[] }>('/admin/dict/cities/', {
        params: { province_id: provinceId }
      });
      return Array.isArray(data) ? data : (data?.results || []);
    },
    enabled: !!provinceId,
    staleTime: Infinity,
  });

  // 获取区县
  const useDistrictQuery = (cityId?: number) => useQuery<District[]>({
    queryKey: ['dict_districts', cityId],
    queryFn: async () => {
      if (!cityId) return [];
      const { data } = await apiClient.get<District[] | { results: District[] }>('/admin/dict/districts/', {
        params: { city_id: cityId }
      });
      return Array.isArray(data) ? data : (data?.results || []);
    },
    enabled: !!cityId,
    staleTime: Infinity,
  });

  // 获取企业所有制分类与标签
  const categoryQuery = useQuery<CompanyCategory[]>({
    queryKey: ['dict_categories'],
    queryFn: async () => {
      const { data } = await apiClient.get<CompanyCategory[] | { results: CompanyCategory[] }>('/admin/dict/categories/');
      return Array.isArray(data) ? data : (data?.results || []);
    },
    staleTime: 1000 * 60 * 60,
  });

  return { provinceQuery, useCityQuery, useDistrictQuery, categoryQuery };
};



