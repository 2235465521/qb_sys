import React, { useState } from 'react';
import { Drawer, List, Checkbox, Button, Space, Tag, Empty, message, Progress } from 'antd';
import { FilePdfOutlined, DownloadOutlined, LoadingOutlined } from '@ant-design/icons';
import { useSearchData } from '@/hooks/useSearchData';
import type { Standard, Company } from '@/types';

interface StandardDrawerProps {
  company: Company | null;
  open: boolean;
  onClose: () => void;
}

const StandardDrawer: React.FC<StandardDrawerProps> = ({ company, open, onClose }) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [packing, setPacking] = useState(false);
  const [progress, setProgress] = useState(0);

  const { useCompanyStandards, zipMutation, checkZipStatus } = useSearchData();
  const { data: standards, isLoading } = useCompanyStandards(company?.id);

  const handleDownload = async () => {
    if (selectedIds.length === 0) {
      message.warning('请至少选择一个标准文件');
      return;
    }

    setPacking(true);
    setProgress(10);
    try {
      const { token } = await zipMutation.mutateAsync(selectedIds);
      
      // 开始轮询
      const timer = setInterval(async () => {
        const statusData = await checkZipStatus(token);
        if (statusData.status === 'done') {
          clearInterval(timer);
          setProgress(100);
          setPacking(false);
          window.location.href = statusData.download_url!;
          message.success('打包完成，开始下载');
        } else if (statusData.status === 'failed') {
          clearInterval(timer);
          setPacking(false);
          message.error('打包失败，请稍后重试');
        } else {
          setProgress(prev => Math.min(prev + 20, 90));
        }
      }, 2000);

    } catch (error) {
      setPacking(false);
      message.error('提交打包任务失败');
    }
  };

  return (
    <Drawer
      title={company ? `${company.name} - 标准资产` : '标准列表'}
      placement="right"
      width={500}
      onClose={onClose}
      open={open}
      extra={
        <Space>
          <Button 
            onClick={() => {
              if (selectedIds.length === (standards?.length || 0)) {
                setSelectedIds([]);
              } else {
                setSelectedIds((standards || []).map(s => s.id));
              }
            }}
            disabled={!standards || standards.length === 0}
          >
            {selectedIds.length === (standards?.length || 0) && (standards?.length || 0) > 0 ? '取消全选' : '一键全选'}
          </Button>
          <Button onClick={() => setSelectedIds([])} disabled={selectedIds.length === 0}>清空</Button>
          <Button 
            type="primary" 
            icon={packing ? <LoadingOutlined /> : <DownloadOutlined />} 
            disabled={selectedIds.length === 0 || packing}
            onClick={handleDownload}
          >
            {packing ? '打包中...' : `打包下载 (${selectedIds.length})`}
          </Button>
        </Space>
      }
    >
      {packing && <Progress percent={progress} status="active" style={{ marginBottom: 16 }} />}

      <List
        loading={isLoading}
        dataSource={Array.isArray(standards) ? standards : []}
        locale={{ emptyText: <Empty description="该企业暂未上传任何标准" /> }}
        renderItem={(item: Standard) => (
          <List.Item
            actions={[
              <Checkbox 
                key="select"
                checked={selectedIds.includes(item.id)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedIds([...selectedIds, item.id]);
                  } else {
                    setSelectedIds(selectedIds.filter(id => id !== item.id));
                  }
                }}
              />
            ]}
          >
            <List.Item.Meta
              avatar={<FilePdfOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />}
              title={<span style={{ fontWeight: 'bold' }}>{item.standard_no}</span>}
              description={
                <Space direction="vertical" size={0}>
                  <span>{item.title}</span>
                  <Space>
                    <Tag color="blue">{item.type_display}</Tag>
                    {item.is_parsed && item.is_parsed !== 'unparsed' && (
                      <Tag color={item.is_parsed === 'indicators_parsed' ? 'purple' : 'green'}>
                        {item.is_parsed === 'indicators_parsed' ? '已解析指标' : '已解析引用'}
                      </Tag>
                    )}
                  </Space>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    </Drawer>
  );
};

export default StandardDrawer;
