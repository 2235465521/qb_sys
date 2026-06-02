import React, { createContext, useContext } from 'react';
import { useTaskPolling, BackgroundTask } from '@/hooks/useTaskPolling';

export type { BackgroundTask };

interface TaskContextType {
  tasks: BackgroundTask[];
  dispatchTask: (token: string, name: string, isCelery?: boolean, apiPath?: string, payload?: any) => void;
  clearDoneTasks: () => void;
  cancelTask: (token: string) => void;
  retryTask: (token: string) => void;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const taskPolling = useTaskPolling();

  return (
    <TaskContext.Provider value={taskPolling}>
      {children}
    </TaskContext.Provider>
  );
};

export const useTaskContext = () => {
  const context = useContext(TaskContext);
  if (!context) {
    throw new Error('useTaskContext must be used within a TaskProvider');
  }
  return context;
};
