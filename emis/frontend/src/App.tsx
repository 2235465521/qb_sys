import { RouterProvider } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { router } from './router';
// HMR Trigger: Register B2B CRM Leads Routing tree
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
});

import { TaskProvider } from '@/store/TaskContext';

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TaskProvider>
        <ConfigProvider 
          locale={zhCN}
          theme={{
            token: {
              colorPrimary: '#0d9488', // Teal 600
              colorSuccess: '#10b981', // Emerald 500
              colorWarning: '#f59e0b', // Amber 500
              colorError: '#ef4444', // Red 500
              colorInfo: '#0ea5e9', // Sky 500
              borderRadius: 10,
              fontFamily: "'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
              colorBgLayout: '#f8fafc', // Slate 50 layout background
            },
            components: {
              Card: {
                borderRadiusLG: 16,
                boxShadow: '0 4px 20px -2px rgba(0,0,0,0.05), 0 2px 8px -1px rgba(0,0,0,0.02)',
              },
              Button: {
                controlHeight: 38,
                borderRadius: 8,
              },
              Input: {
                controlHeight: 38,
                borderRadius: 8,
              },
              Select: {
                controlHeight: 38,
                borderRadius: 8,
              },
              Table: {
                borderRadius: 12,
                headerBg: '#f8fafc',
              },
            }
          }}
        >
          <RouterProvider router={router} />
        </ConfigProvider>
      </TaskProvider>
    </QueryClientProvider>
  );
}

export default App;
