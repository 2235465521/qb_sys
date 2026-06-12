import React, { useState } from 'react';
import { Drawer, List, Button, Space, Tag, Empty, message, Progress, Tabs, Modal, Tooltip } from 'antd';
import { FilePdfOutlined, DownloadOutlined, LoadingOutlined, DeleteOutlined, ShoppingCartOutlined, PlusOutlined } from '@ant-design/icons';
import { useSearchData } from '@/hooks/useSearchData';
import type { Standard, Company } from '@/types';
import StandardListItem from './StandardListItem';

interface StandardDrawerProps {
  company: Company | null;
  open: boolean;
  onClose: () => void;
}

const StandardDrawer: React.FC<StandardDrawerProps> = ({ company, open, onClose }) => {
  const [selectedIds, setSelectedIds] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<string>('all');
  const [confirmModalVisible, setConfirmModalVisible] = useState(false);
  const [packing, setPacking] = useState(false);
  const [progress, setProgress] = useState(0);

  const { useCompanyStandards, useCompanyFederatedStandards, zipMutation, checkZipStatus } = useSearchData();
  const { data: localStandards, isLoading: localLoading } = useCompanyStandards(company?.id);
  const { data: federatedData, isLoading: fedLoading } = useCompanyFederatedStandards(company?.id);

  const standards = React.useMemo(() => {
    const arr: any[] = [...(localStandards || [])].map(s => ({ ...s, is_local: true }));
    const existingStdNos = new Set(arr.map(s => String(s.standard_no || '').trim().toUpperCase()));
    const existingTitles = new Set(arr.map(s => String(s.title || '').trim().toUpperCase()));

    if (federatedData && federatedData.standards) {
      const mappedFed = federatedData.standards.map((s: any) => {
        let mappedType = 'industry'; // Default unclassified to industry
        const stdNo = String(s.standard_no || '').trim().toUpperCase();
        
        // 自动提取标准号前缀作为展示标签 (e.g. GB/T, DB, T)
        let displayTag = '标准';
        const match = stdNo.match(/^([A-Z]+(\/[A-Z]+)?)/);
        if (match) {
           displayTag = match[1];
        } else {
           displayTag = s.type || '标准';
        }

        // 归类到对应的 Tab
        if (stdNo.startsWith('GB')) mappedType = 'national';
        else if (stdNo.startsWith('DB')) mappedType = 'local';
        else if (stdNo.startsWith('TB') || stdNo.startsWith('T/') || stdNo.match(/^T\s/)) mappedType = 'group';
        
        return {
          ...s,
          id: `fed_${s.standard_no}`, // string ID for React keys, but not selectable for ZIP
          type: mappedType,
          type_display: displayTag, 
          is_parsed: 'unparsed',
          is_local: false,
          title: s.title || '无标题'
        };
      }).filter((s: any) => {
        const stdNo = String(s.standard_no || '').trim().toUpperCase();
        const title = String(s.title || '').trim().toUpperCase();
        // 简单去重：如果本地库已经有该标准号或相同标题的记录，则不在前端重复展示
        if (stdNo && existingStdNos.has(stdNo)) return false;
        if (title && existingTitles.has(title)) return false;
        return true;
      });
      arr.push(...mappedFed);
    }
    return arr;
  }, [localStandards, federatedData]);

  const isLoading = localLoading || fedLoading;

  // 1. 根据标签过滤当前展示的标准列表
  const filteredStandards = React.useMemo(() => {
    if (!standards) return [];
    if (activeTab === 'all') return standards;
    return standards.filter((s) => s.type === activeTab);
  }, [standards, activeTab]);

  // 2. 一键全选/取消全选当前可见列表 (支持全量混合标准)
  const handleToggleSelectAll = () => {
    const filteredIds = filteredStandards.map((s) => s.id);
    const allSelected = filteredIds.length > 0 && filteredIds.every((id) => selectedIds.includes(id));

    if (allSelected) {
      // 取消全选当前可见列表的项
      setSelectedIds((prev) => prev.filter((id) => !filteredIds.includes(id)));
    } else {
      // 全选当前可见列表的项，并去重合并
      setSelectedIds((prev) => {
        const nextSet = new Set([...prev, ...filteredIds]);
        return Array.from(nextSet);
      });
    }
  };

  // 3. 调用后端接口开始打包下载
  const executeDownload = async () => {
    if (selectedIds.length === 0) {
      message.warning('请至少选择一个标准文件');
      return;
    }

    setConfirmModalVisible(false);
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
          if (statusData.download_url) {
            window.location.href = statusData.download_url;
          }
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

  // 选中的标准对象列表（购物车清单显示）
  const selectedStandards = React.useMemo(() => {
    if (!standards) return [];
    return standards.filter((s) => selectedIds.includes(s.id));
  }, [standards, selectedIds]);

  const handleOpenConfirm = () => {
    if (selectedIds.length === 0) {
      message.warning('请选择要下载的标准文件');
      return;
    }
    setConfirmModalVisible(true);
  };

  const handleRemoveFromCart = (id: number) => {
    setSelectedIds((prev) => prev.filter((item) => item !== id));
  };

  const handleClearCart = () => {
    setSelectedIds([]);
    setConfirmModalVisible(false);
  };

  // 各分类标签标准数量统计
  const typeCounts = React.useMemo(() => {
    const counts = { all: 0, enterprise: 0, national: 0, industry: 0, local: 0, group: 0 };
    if (!standards) return counts;
    counts.all = standards.length;
    standards.forEach((s) => {
      if (s.type in counts) {
        counts[s.type as keyof typeof counts]++;
      }
    });
    return counts;
  }, [standards]);

  const tabItems = [
    { label: `全部 (${typeCounts.all})`, key: 'all' },
    { label: `企标 (${typeCounts.enterprise})`, key: 'enterprise' },
    { label: `国标 (${typeCounts.national})`, key: 'national' },
    { label: `行标 (${typeCounts.industry})`, key: 'industry' },
    { label: `地标 (${typeCounts.local})`, key: 'local' },
    { label: `团标 (${typeCounts.group})`, key: 'group' },
  ];

  return (
    <>
      <Drawer
        title={company ? `${company.name} - 标准资产` : '标准列表'}
        placement="right"
        width={520}
        onClose={onClose}
        open={open}
        extra={
          <Space>
            <Button 
              onClick={handleToggleSelectAll}
              disabled={filteredStandards.length === 0}
            >
              {filteredStandards.length > 0 && filteredStandards.every((item) => selectedIds.includes(item.id))
                ? '取消当前全选'
                : '当前列表全选'}
            </Button>
            <Button onClick={() => setSelectedIds([])} disabled={selectedIds.length === 0}>清空</Button>
            <Button 
              type="primary" 
              icon={packing ? <LoadingOutlined /> : <DownloadOutlined />} 
              disabled={selectedIds.length === 0 || packing}
              onClick={handleOpenConfirm}
              style={{ background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)', borderColor: '#13c2c2' }}
            >
              {packing ? '打包中...' : `打包下载 (${selectedIds.length})`}
            </Button>
          </Space>
        }
      >
        {packing && <Progress percent={progress} status="active" style={{ marginBottom: 16 }} />}

        {/* 顶部标签筛选 */}
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab} 
          items={tabItems} 
          style={{ marginBottom: 8 }}
        />

        <List
          loading={isLoading}
          dataSource={filteredStandards}
          pagination={{ 
            pageSize: 20, 
            showSizeChanger: false, 
            size: 'small',
            showTotal: (total) => `共 ${total} 条`
          }}
          locale={{ emptyText: <Empty description="当前类别下无任何标准文件" /> }}
          renderItem={(item: any) => (
            <StandardListItem 
              item={item} 
              selectedIds={selectedIds} 
              onSelect={(id, checked) => {
                if (checked) {
                  setSelectedIds([...selectedIds, id]);
                } else {
                  setSelectedIds(selectedIds.filter(sid => sid !== id));
                }
              }} 
            />
          )}
        />
      </Drawer>

      {/* 确认清单 Modal */}
      <Modal
        title={
          <Space>
            <ShoppingCartOutlined style={{ color: '#13c2c2', fontSize: 20 }} />
            <span>确认下载清单</span>
            <Tag color="cyan">已选 {selectedIds.length} 个标准</Tag>
          </Space>
        }
        open={confirmModalVisible}
        onCancel={() => setConfirmModalVisible(false)}
        width={600}
        footer={[
          <Button key="clear" danger onClick={handleClearCart} style={{ float: 'left' }}>
            清空列表
          </Button>,
          <Button key="back" icon={<PlusOutlined />} onClick={() => setConfirmModalVisible(false)}>
            继续添加
          </Button>,
          <Button 
            key="submit" 
            type="primary" 
            icon={<DownloadOutlined />}
            onClick={executeDownload}
            style={{ background: 'linear-gradient(135deg, #13c2c2 0%, #0097a7 100%)', borderColor: '#13c2c2' }}
          >
            确认打包下载
          </Button>
        ]}
      >
        <div style={{ maxHeight: 400, overflowY: 'auto', padding: '8px 0' }}>
          <List
            dataSource={selectedStandards}
            locale={{ emptyText: <Empty description="确认清单为空" /> }}
            renderItem={(item: Standard) => (
              <List.Item
                actions={[
                  <Tooltip key="delete" title="从清单中移除">
                    <Button 
                      type="text" 
                      danger 
                      icon={<DeleteOutlined />} 
                      onClick={() => handleRemoveFromCart(item.id)}
                    />
                  </Tooltip>
                ]}
              >
                <List.Item.Meta
                  avatar={<FilePdfOutlined style={{ fontSize: 20, color: '#ff4d4f' }} />}
                  title={<span style={{ fontWeight: 500 }}>{item.standard_no}</span>}
                  description={
                    <Space size={8}>
                      <span style={{ fontSize: 13, color: '#555' }}>{item.title}</span>
                      <Tag color="blue">{item.type_display}</Tag>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </div>
      </Modal>
    </>
  );
};

export default StandardDrawer;
