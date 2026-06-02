import { useState, useEffect, useRef } from 'react';
import { notification, message } from 'antd';
import apiClient from '@/api/client';

export interface BackgroundTask {
  id: string;
  name: string;
  status: 'running' | 'done' | 'failed';
  progress: number;
  downloadUrl?: string;
  error?: string;
  isCelery?: boolean;
  apiPath?: string;
  payload?: any;
}

const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes timeout

export const useTaskPolling = () => {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const intervalsRef = useRef<Record<string, { intervalId: any; startTime: number }>>({});

  const cancelTask = (token: string) => {
    if (intervalsRef.current[token]) {
      clearInterval(intervalsRef.current[token].intervalId);
      delete intervalsRef.current[token];
    }
    setTasks(prev => prev.filter(t => t.id !== token));
  };

  const clearDoneTasks = () => {
    // Clear only completed or failed tasks, leaving running tasks intact
    setTasks(prev => prev.filter(t => t.status === 'running'));
  };

  const dispatchTask = (
    token: string,
    name: string,
    isCelery?: boolean,
    apiPath?: string,
    payload?: any
  ) => {
    const newTask: BackgroundTask = {
      id: token,
      name,
      status: 'running',
      progress: 10,
      isCelery,
      apiPath,
      payload,
    };

    setTasks(prev => {
      if (prev.some(t => t.id === token)) return prev;
      return [...prev, newTask];
    });

    const startTime = Date.now();

    const intervalId = setInterval(async () => {
      // 1. Timeout Check
      if (Date.now() - startTime > TIMEOUT_MS) {
        clearInterval(intervalId);
        delete intervalsRef.current[token];

        setTasks(prev => prev.map(t => 
          t.id === token ? { ...t, status: 'failed', error: '任务执行超时，请稍后再试' } : t
        ));
        notification.error({
          message: '任务执行超时',
          description: `${name} 执行已超时，请稍后再试。`,
        });
        return;
      }

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
          }
        } else {
          const stdStatus = res.data.status;
          if (stdStatus === 'done') {
            mappedStatus = 'done';
          } else if (stdStatus === 'failed') {
            mappedStatus = 'failed';
          } else {
            mappedStatus = 'running';
          }
        }

        if (mappedStatus === 'done') {
          clearInterval(intervalId);
          delete intervalsRef.current[token];

          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'done', progress: 100, downloadUrl } : t
          ));

          notification.success({
            message: '打包任务完成',
            description: `${name} 已就绪。`,
            duration: 5,
          });

          if (downloadUrl) {
            window.open(downloadUrl, '_blank');
          }
        } else if (mappedStatus === 'failed') {
          clearInterval(intervalId);
          delete intervalsRef.current[token];

          setTasks(prev => prev.map(t => 
            t.id === token ? { ...t, status: 'failed', error } : t
          ));

          notification.error({
            message: '打包任务失败',
            description: error || '发生了未知错误',
          });
        } else {
          // 优先使用后端返回的真实进度，若没有则本地模拟递增（上限 85%，防止超过完成前跳到 100%）
          const serverProgress = typeof res.data.progress === 'number' ? res.data.progress : null;
          setTasks(prev => prev.map(t => {
            if (t.id === token) {
              const nextProgress = serverProgress !== null
                ? serverProgress
                : (t.progress < 85 ? t.progress + 5 : t.progress);
              return { ...t, progress: nextProgress };
            }
            return t;
          }));
        }
      } catch (err: any) {
        console.error('Polling error:', err);
      }
    }, 2000);

    intervalsRef.current[token] = { intervalId, startTime };
  };

  const retryTask = async (token: string) => {
    const task = tasks.find(t => t.id === token);
    if (!task || !task.apiPath) {
      message.error('无法重试：缺少任务请求上下文');
      return;
    }

    try {
      const hide = message.loading('正在重新提交任务...', 0);
      const { data } = await apiClient.post(task.apiPath, task.payload);
      hide();
      message.success('已重新提交任务，正在为您排队打包...');

      // Remove old failed task
      cancelTask(token);

      // Dispatch new task
      const newToken = data.task_id || data.token;
      dispatchTask(newToken, task.name, task.isCelery, task.apiPath, task.payload);
    } catch (err: any) {
      message.destroy();
      const errMsg = err.response?.data?.error || '重新提交任务失败，请稍后重试';
      message.error(errMsg);
    }
  };

  useEffect(() => {
    return () => {
      Object.values(intervalsRef.current).forEach(item => clearInterval(item.intervalId));
    };
  }, []);

  return {
    tasks,
    dispatchTask,
    clearDoneTasks,
    cancelTask,
    retryTask,
  };
};
