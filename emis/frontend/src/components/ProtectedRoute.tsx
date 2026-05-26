import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { Spin } from 'antd';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, requireAdmin = false }) => {
  const { isLoading, isAdmin } = useAuth();
  const location = useLocation();

  const hasToken = !!localStorage.getItem('access_token');
  
  if (hasToken && isLoading) {
    return (
      <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#f5f5f5' }}>
        <Spin size="large" tip="正在安全校验身份中..." />
      </div>
    );
  }

  if (!hasToken) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/client/search" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
