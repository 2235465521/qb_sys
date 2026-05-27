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
        <ConfigProvider locale={zhCN}>
          <RouterProvider router={router} />
        </ConfigProvider>
      </TaskProvider>
    </QueryClientProvider>
  );
}

export default App;
