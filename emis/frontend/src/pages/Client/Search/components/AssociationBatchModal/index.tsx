import React from 'react';
import { Modal, Button, Space, Row, Col, Card, Statistic, Popconfirm } from 'antd';
import {
  FileExcelOutlined,
  CloudDownloadOutlined,
  RollbackOutlined,
  CheckCircleOutlined,
  FileDoneOutlined,
  DeploymentUnitOutlined,
  BankOutlined,
} from '@ant-design/icons';
import { useAssociationBatch } from '@/hooks/useAssociationBatch';
import { UploadArea } from './UploadArea';
import { SummaryTable } from './SummaryTable';
import { DetailDrawer } from './DetailDrawer';

interface AssociationBatchModalProps {
  open: boolean;
  onCancel: () => void;
}

export const AssociationBatchModal: React.FC<AssociationBatchModalProps> = ({ open, onCancel }) => {
  const {
    loading,
    exporting,
    result,
    selectedNames,
    setSelectedNames,
    activeDetailItem,
    setActiveDetailItem,
    queryByFile,
    queryByNames,
    exportMergedExcel,
    reset,
  } = useAssociationBatch();

  const handleClose = () => {
    onCancel();
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 16, fontWeight: 600 }}>
          <FileExcelOutlined style={{ color: '#0d9488', fontSize: 18 }} />
          <span>社团/协会名单批量查标与合并导出</span>
        </div>
      }
      open={open}
      onCancel={handleClose}
      width={1100}
      destroyOnClose
      footer={
        result ? (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
            <Popconfirm
              title="确定重新上传名单？"
              description="当前解析和查询结果将被清空。"
              onConfirm={reset}
              okText="确定"
              cancelText="取消"
            >
              <Button icon={<RollbackOutlined />}>重新导入名单</Button>
            </Popconfirm>

            <Space>
              <Button onClick={handleClose}>关闭</Button>
              <Button
                type="primary"
                icon={<CloudDownloadOutlined />}
                loading={exporting}
                disabled={selectedNames.length === 0}
                onClick={() => exportMergedExcel()}
                style={{
                  background: 'linear-gradient(135deg, #13c2c2 0%, #0d9488 100%)',
                  borderColor: '#0d9488',
                  borderRadius: 16,
                  padding: '0 20px',
                  fontWeight: 500,
                  boxShadow: '0 2px 8px rgba(13, 148, 136, 0.2)',
                }}
              >
                导出合并标准大表 ({selectedNames.length} 家协会)
              </Button>
            </Space>
          </div>
        ) : null
      }
    >
      {!result ? (
        <UploadArea
          loading={loading}
          onFileSelect={queryByFile}
          onTextSubmit={queryByNames}
        />
      ) : (
        <div>
          <Row gutter={12} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
                <Statistic
                  title={<span style={{ fontSize: 12, color: '#64748b' }}>识别社团名单</span>}
                  value={result.total_input}
                  suffix="家"
                  valueStyle={{ fontSize: 20, fontWeight: 600, color: '#0f172a' }}
                  prefix={<BankOutlined style={{ color: '#0d9488', fontSize: 16 }} />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
                <Statistic
                  title={<span style={{ fontSize: 12, color: '#64748b' }}>命中工商档案</span>}
                  value={result.matched_count}
                  suffix="家"
                  valueStyle={{ fontSize: 20, fontWeight: 600, color: '#16a34a' }}
                  prefix={<CheckCircleOutlined style={{ color: '#16a34a', fontSize: 16 }} />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ background: '#f8fafc', borderRadius: 8 }}>
                <Statistic
                  title={<span style={{ fontSize: 12, color: '#64748b' }}>覆盖标准总资产</span>}
                  value={result.total_standards_count}
                  suffix="项"
                  valueStyle={{ fontSize: 20, fontWeight: 600, color: '#0d9488' }}
                  prefix={<DeploymentUnitOutlined style={{ color: '#0d9488', fontSize: 16 }} />}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card size="small" style={{ background: '#f0fdf4', borderRadius: 8, borderColor: '#bbf7d0' }}>
                <Statistic
                  title={<span style={{ fontSize: 12, color: '#15803d' }}>已勾选导出协会</span>}
                  value={selectedNames.length}
                  suffix={`/ ${result.total_input}`}
                  valueStyle={{ fontSize: 20, fontWeight: 600, color: '#15803d' }}
                  prefix={<FileDoneOutlined style={{ color: '#15803d', fontSize: 16 }} />}
                />
              </Card>
            </Col>
          </Row>

          <SummaryTable
            items={result.items}
            selectedNames={selectedNames}
            onSelectionChange={setSelectedNames}
            onViewDetails={(item) => setActiveDetailItem(item)}
          />

          <DetailDrawer
            item={activeDetailItem}
            open={!!activeDetailItem}
            onClose={() => setActiveDetailItem(null)}
          />
        </div>
      )}
    </Modal>
  );
};
