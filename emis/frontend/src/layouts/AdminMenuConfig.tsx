import {
  DashboardOutlined,
  BankOutlined,
  SettingOutlined,
  MessageOutlined,
  UserOutlined,
  FileTextOutlined,
  TeamOutlined,
  LineChartOutlined,
  CustomerServiceOutlined,
  AppstoreOutlined,
  InteractionOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';

export const adminMenuItems: MenuProps['items'] = [
  {
    key: '/admin/dashboard',
    icon: <DashboardOutlined />,
    label: '管理控制台',
  },
  {
    key: 'core_business',
    icon: <AppstoreOutlined />,
    label: '核心业务管理',
    children: [
      {
        key: '/admin/companies',
        icon: <BankOutlined />,
        label: '企业库管理',
      },
      {
        key: '/admin/standards',
        icon: <FileTextOutlined />,
        label: '企业标准管理',
      },
      {
        key: '/admin/references',
        icon: <LineChartOutlined />,
        label: '引用记录管理',
      },
    ],
  },
  {
    key: 'customer_marketing',
    icon: <InteractionOutlined />,
    label: '客户营销中心',
    children: [
      {
        key: '/admin/leads',
        icon: <CustomerServiceOutlined />,
        label: '线索客户管理',
      },
      {
        key: '/admin/members',
        icon: <TeamOutlined />,
        label: '会员信息管理',
      },
      {
        key: '/admin/sms-templates',
        icon: <MessageOutlined />,
        label: '短信模板管理',
      },
    ],
  },
  {
    key: 'system_settings',
    icon: <ToolOutlined />,
    label: '系统基础设置',
    children: [
      {
        key: '/admin/users',
        icon: <UserOutlined />,
        label: '系统用户管理',
      },
      {
        key: '/admin/dict',
        icon: <SettingOutlined />,
        label: '数据字典',
      },
    ],
  },
];
