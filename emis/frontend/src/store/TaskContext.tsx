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
  dispatchTask: (token: string, name: string, isCelery?: boolean) => void;
  clearDoneTasks: () => void;
  cancelTask: (token: string) => void;
}

const TaskContext = createContext<TaskContextType | undefined>(undefined);

export const TaskProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const intervalsRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const dispatchTask = (token: string, name: string, isCelery?: boolean) => {
    setTasks(prev => [...prev, { id: token, name, status: 'running', progress: 10 }]);

    const intervalId = setInterval(async () => {
      try {
        const url = isCelery
          ? `/client/standards/pack-tasks/${token}/`
          : `/client/standards/pack/${token}/status/`;

        const res = await apiClient.get<{ status: string; download_url?: string; error?: string }>(url);

        let mappedStatus: 'running' | 'done' | 'failed' = 'running';
        let downloadUrl = res.data.download_url;
        let error = res.data.error;

        if (isCelery) {
          const celeryStatus = res.data.status;
          if (celeryStatus === 'SUCCESS') {
            mappedStatus = 'done';
          } else if (celeryStatus === 'FAILURE' || celeryStatus === 'REVOKED') {
            mappedStatus = 'failed';
            error = res.data.error || '打包任务失败或被撤销';
          } else {
            mappedStatus = 'running';
            setTasks(prev => prev.map(t => {
              if (t.id === token) {
                const nextProgress = t.progress < 90 ? t.progress + 10 : t.progress;
                return { ...t, progress: nextProgress };
              }
              return t;
            }));
            return;
          }
        } else {
          const stdStatus = res.data.status;
          if (stdStatus === 'done') {
            mappedStatus = 'done';
          } else if (stdStatus === 'failed') {
            mappedStatus = 'failed';
          } else {
            mappedStatus = 'running';
            setTasks(prev => prev.map(t => {
              if (t.id === token) {
                const nextProgress = t.progress < 90 ? t.progress + 10 : t.progress;
                return { ...t, progress: nextProgress };
              }
              return t;
            }));
            return;
          }
        }

        if (mappedStatus === 'done') {
          clearInterval(intervalsRef.current[token]);
          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'done', progress: 100, downloadUrl } : t
          ));

          notification.success({
            message: '打包任务完成',
            description: `${name} 已就绪。`,
            btn: (
              <a href={downloadUrl} target="_blank" rel="noreferrer">
                点击下载
              </a>
            ),
            duration: 0,
          });
          
          if (downloadUrl) {
            window.open(downloadUrl, '_blank');
          }
        } else if (mappedStatus === 'failed') {
          clearInterval(intervalsRef.current[token]);
          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'failed', error } : t
          ));
          notification.error({
            message: '打包任务失败',
            description: error || '发生了未知错误',
          });
        }
      } catch (err) {
        clearInterval(intervalsRef.current[token]);
        setTasks(prev => prev.map(t => 
          t.id === token ? { ...t, status: 'failed', error: '网络错误' } : t
        ));
      }
    }, 2000);

    intervalsRef.current[token] = intervalId;
  };

  const clearDoneTasks = () => {
    setTasks(prev => prev.filter(t => t.status === 'running'));
  };

  const cancelTask = (token: string) => {
    if (intervalsRef.current[token]) {
      clearInterval(intervalsRef.current[token]);
    }
    setTasks(prev => prev.filter(t => t.id !== token));
  };

  useEffect(() => {
    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  }, []);

  return (
    <TaskContext.Provider value={{ tasks, dispatchTask, clearDoneTasks, cancelTask }}>
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
