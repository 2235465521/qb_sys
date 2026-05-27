import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { notification } from 'antd';
import apiClient from '@/api/client';

export interface BackgroundTask {
  id: string;
  name: string;
  status: 'running' | 'done' | 'failed';
  progress: number;
  downloadUrl?: string;
  error?: string;
}

interface TaskContextType {
  tasks: BackgroundTask[];
  dispatchTask: (token: string, name: string) => void;
  clearDoneTasks: () => void;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const intervalsRef = useRef<Record<string, NodeJS.Timeout>>({});

  const dispatchTask = (token: string, name: string) => {
    setTasks(prev => [...prev, { id: token, name, status: 'running', progress: 10 }]);

    const intervalId = setInterval(async () => {
      try {
        const res = await apiClient.get<{ status: string; download_url?: string; error?: string }>(
          `/client/standards/pack/${token}/status/`
        );

        if (res.data.status === 'running') {
          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, progress: 60 } : t
          ));
        } else if (res.data.status === 'done') {
          clearInterval(intervalsRef.current[token]);
          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'done', progress: 100, downloadUrl: res.data.download_url } : t
          ));

          notification.success({
            message: '打包任务完成',
            description: `${name} 已就绪。`,
            btn: (
              <a href={res.data.download_url} target="_blank" rel="noreferrer">
                点击下载
              </a>
            ),
            duration: 0,
          });
          
          // Optionally auto download
          if (res.data.download_url) {
            window.open(res.data.download_url, '_blank');
          }
        } else if (res.data.status === 'failed') {
          clearInterval(intervalsRef.current[token]);
          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'failed', error: res.data.error } : t
          ));
          notification.error({
            message: '打包任务失败',
            description: res.data.error || '发生了未知错误',
          });
        }
      } catch (err) {
        clearInterval(intervalsRef.current[token]);
        setTasks(prev => prev.map(t => 
          t.id === token ? { ...t, status: 'failed', error: '网络错误' } : t
        ));
      }
    }, 1500);

    intervalsRef.current[token] = intervalId;
  };

  const clearDoneTasks = () => {
    setTasks(prev => prev.filter(t => t.status === 'running'));
  };

  useEffect(() => {
    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  }, []);

  return (
    <TaskContext.Provider value={{ tasks, dispatchTask, clearDoneTasks }}>
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
