import React from 'react';
import { List, Checkbox, Button, Space, Tag, Tooltip } from 'antd';
import { FilePdfOutlined, DownloadOutlined } from '@ant-design/icons';


interface StandardListItemProps {
  item: any;
  selectedIds: any[];
  onSelect: (id: any, checked: boolean) => void;
}

const StandardListItem: React.FC<StandardListItemProps> = ({ item, selectedIds, onSelect }) => {
  return (
    <List.Item
      actions={[
        <Checkbox 
          key="select"
          checked={selectedIds.includes(item.id)}
          onChange={(e) => onSelect(item.id, e.target.checked)}
        />,
        !item.is_local && item.file_path && (
          <Tooltip title="下载原文" key="download">
            <Button 
              type="text" 
              size="small" 
              icon={<DownloadOutlined style={{color: '#13c2c2'}} />} 
              href={`/api/client/search/federated_download/?file_path=${encodeURIComponent(item.file_path)}`} 
              target="_blank"
            />
          </Tooltip>
        ),
        !item.is_local && item.rank_order && (
          <Tag color="orange" style={{ margin: 0 }} key="tag">
            第{item.rank_order}名
          </Tag>
        )
      ].filter(Boolean)}
    >
      <List.Item.Meta
        avatar={<FilePdfOutlined style={{ fontSize: 24, color: item.is_local ? '#ff4d4f' : '#8c8c8c' }} />}
        title={
          <span style={{ fontWeight: 'bold' }}>
            {item.standard_no} 
            {item.status && (
              <Tag 
                color={item.status === '现行' || item.status === 'active' || item.status === '活跃' ? 'green' : 'default'} 
                style={{marginLeft: 8, fontSize: 12}}
              >
                {item.status === 'active' ? '活跃' : item.status}
              </Tag>
            )}
          </span>
        }
        description={
          <Space direction="vertical" size={0}>
            <span>{item.title}</span>
            <Space>
              <Tag color="blue">{item.type_display}</Tag>
              {item.is_local && item.is_parsed && item.is_parsed !== 'unparsed' && (
                <Tag color={item.is_parsed === 'indicators_parsed' ? 'purple' : 'green'}>
                  {item.is_parsed === 'indicators_parsed' ? '已解析指标' : '已解析引用'}
                </Tag>
              )}
            </Space>
          </Space>
        }
      />
    </List.Item>
  );
};

export default StandardListItem;
