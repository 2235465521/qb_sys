/**
 * 通用跨浏览器安全下载工具函数
 * 解决 Edge / Chrome / Firefox 等浏览器在异步上下文下拦截 window.open 的问题
 */

export const triggerFileDownload = (url: string, filename?: string): void => {
  try {
    const link = document.createElement('a');
    link.href = url;
    if (filename) {
      link.setAttribute('download', filename);
    } else {
      link.setAttribute('download', '');
    }
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    setTimeout(() => {
      link.remove();
    }, 1000);
  } catch (err) {
    console.warn('[Download] a.click() failed, fallback to iframe:', err);
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(() => {
      iframe.remove();
    }, 30000);
  }
};

export const triggerBlobDownload = (blob: Blob, filename: string): void => {
  const downloadUrl = window.URL.createObjectURL(blob);
  triggerFileDownload(downloadUrl, filename);
  setTimeout(() => {
    window.URL.revokeObjectURL(downloadUrl);
  }, 10000);
};
