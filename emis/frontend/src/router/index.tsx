import { createBrowserRouter, Navigate } from 'react-router-dom';
import ClientLayout from '@/layouts/ClientLayout';
import AdminLayout from '@/layouts/AdminLayout';
import LoginPage from '@/pages/Login/index';
import RegisterPage from '@/pages/Register/index';
import ProtectedRoute from '@/components/ProtectedRoute';

// 后台管理页面
import AdminDashboard from '@/pages/Admin/Dashboard';
import CompanyList from '@/pages/Admin/Companies';
import StandardsManager from '@/pages/Admin/Standards';
import AdminReferencesPage from '@/pages/Admin/References';
import AdminLeadsPage from '@/pages/Admin/Leads';
import MemberAdminPage from '@/pages/Admin/Members';
import DictManager from '@/pages/Admin/Dict';
import SmsTemplates from '@/pages/Admin/SmsTemplates';
import AdminUsersManager from '@/pages/Admin/Users';
// 前台应用页面
import CompanySearch from '@/pages/Client/Search';
import ReferenceAnalysis from '@/pages/Client/Analysis';
import MemberCenter from '@/pages/Client/Members';
import SearchStandardsPage from '@/pages/Client/SearchStandards';
import TrendDashboard from '@/pages/Client/Trends';
import StandardGraphPage from '@/pages/Client/StandardGraph';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/register',
    element: <RegisterPage />,
  },
  {
    path: '/',
    element: <Navigate to="/client/search" replace />,
  },
  {
    path: '/client',
    element: (
      <ProtectedRoute>
        <ClientLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: '', element: <Navigate to="search" replace /> },
      { path: 'search', element: <CompanySearch /> },
      { path: 'standards', element: <SearchStandardsPage /> },
      { path: 'graph', element: <StandardGraphPage /> },
      { path: 'analysis', element: <ReferenceAnalysis /> },
      { path: 'trends', element: <TrendDashboard /> },
      { path: 'members', element: <MemberCenter /> },
    ]
  },
  {
    path: '/admin',
    element: (
      <ProtectedRoute requireAdmin>
        <AdminLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: '', element: <Navigate to="dashboard" replace /> },
      { path: 'dashboard', element: <AdminDashboard /> },
      { path: 'trends', element: <Navigate to="/client/trends" replace /> },
      { path: 'companies', element: <CompanyList /> },
      { path: 'standards', element: <StandardsManager /> },
      { path: 'references', element: <AdminReferencesPage /> },
      { path: 'leads', element: <AdminLeadsPage /> },
      { path: 'members', element: <MemberAdminPage /> },
      { path: 'users', element: <AdminUsersManager /> },
      { path: 'dict', element: <DictManager /> },
      { path: 'sms-templates', element: <SmsTemplates /> },
    ]
  }
]);
