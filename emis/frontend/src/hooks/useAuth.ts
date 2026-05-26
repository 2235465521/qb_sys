import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/client';

export interface UserInfo {
  username: string;
  real_name: string;
  role: 'superadmin' | 'admin' | 'operator';
  is_superuser: boolean;
}

export const useAuth = () => {
  const token = localStorage.getItem('access_token');

  const { data: user, isLoading, error, refetch } = useQuery<UserInfo>({
    queryKey: ['currentUser'],
    queryFn: async () => {
      const { data } = await apiClient.get<UserInfo>('/auth/me/');
      return data;
    },
    enabled: !!token,
    staleTime: 1000 * 60 * 15, // 15 minutes cache
    gcTime: 1000 * 60 * 30, // 30 minutes gc
    retry: false,
  });

  const isAuthenticated = !!token && !!user;

  return {
    user,
    isLoading: !!token && isLoading,
    error,
    isAuthenticated,
    refetch,
    isAdmin: user ? ['superadmin', 'admin', 'operator'].includes(user.role) : false,
  };
};
