import React, { useEffect } from 'react';
import { Modal, Form, Input, Select, DatePicker } from 'antd';
import type { Standard } from '@/types';
import dayjs from 'dayjs';

interface EditModalProps {
  open: boolean;
  editingStandard: Standard | null;
  onCancel: () => void;
  onSave: (values: Partial<Standard>) => void;
  confirmLoading: boolean;
}

const EditModal: React.FC<EditModalProps> = ({
  open,
  editingStandard,
  onCancel,
  onSave,
  confirmLoading,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open && editingStandard) {
      const values = {
        ...editingStandard,
        publish_date: editingStandard.publish_date ? dayjs(editingStandard.publish_date) : null,
        implement_date: editingStandard.implement_date ? dayjs(editingStandard.implement_date) : null,
      };
      form.setFieldsValue(values);
    } else {
      form.resetFields();
    }
  }, [open, editingStandard, form]);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      const formattedValues = {
        ...values,
        publish_date: values.publish_date ? values.publish_date.format('YYYY-MM-DD') : null,
        implement_date: values.implement_date ? values.implement_date.format('YYYY-MM-DD') : null,
      };
      onSave({ ...editingStandard, ...formattedValues });
    } catch (e) {
      // Form validation failed
    }
  };

  return (
    <Modal
      title={<span style={{ fontWeight: 'bold', fontSize: 16 }}>修改企业标准</span>}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      confirmLoading={confirmLoading}
      destroyOnClose
      width={480}
      okText="保存修改"
      cancelText="取消"
    >
      <Form
        form={form}
        layout="vertical"
        style={{ marginTop: 16 }}
      >
        <Form.Item
          name="standard_no"
          label="标准编号"
          rules={[{ required: true, message: '请输入标准编号' }]}
        >
          <Input placeholder="例如: Q/XMBL001-2021" />
        </Form.Item>
        <Form.Item
          name="title"
          label="标准名称"
          rules={[{ required: true, message: '请输入标准名称' }]}
        >
          <Input placeholder="请输入标准名称" />
        </Form.Item>
        <Form.Item
          name="status"
          label="标准状态"
          rules={[{ required: true, message: '请选择标准状态' }]}
        >
          <Select placeholder="请选择标准状态">
            <Select.Option value="active">正常运行 (现行)</Select.Option>
            <Select.Option value="deprecated">已废止</Select.Option>
            <Select.Option value="draft">草案</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item
          name="publish_date"
          label="发布时间"
        >
          <DatePicker style={{ width: '100%', borderRadius: 8 }} placeholder="请选择发布时间" />
        </Form.Item>
        <Form.Item
          name="implement_date"
          label="实施时间"
        >
          <DatePicker style={{ width: '100%', borderRadius: 8 }} placeholder="请选择实施时间" />
        </Form.Item>
        <Form.Item
          name="ics"
          label="ICS分类号"
        >
          <Input placeholder="请输入ICS分类号, 如 35.240" />
        </Form.Item>
        <Form.Item
          name="ccs"
          label="CCS分类号"
        >
          <Input placeholder="请输入CCS分类号, 如 L67" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default EditModal;
