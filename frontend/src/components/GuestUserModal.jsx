import { useState, useEffect } from 'preact/hooks';
import { Modal, Form, Input, Button, Space, Typography, Tooltip } from 'antd';
import { UserOutlined, IdcardOutlined } from '@ant-design/icons';
import { makeAuthenticatedRequest } from '../utils/auth';

const { Text } = Typography;

export function GuestUserModal({ 
  visible, 
  onClose, 
  onSuccess, 
  onError, 
  onDataChange,
  data 
}) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [generatedId, setGeneratedId] = useState('');

  // Generate a random GUID when modal opens
  useEffect(() => {
    if (visible) {
      const newId = generateGuid();
      setGeneratedId(newId);
      form.setFieldsValue({
        guestId: newId
      });
    }
  }, [visible, form]);

  const generateGuid = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };

  const handleGenerateNewId = () => {
    const newId = generateGuid();
    setGeneratedId(newId);
    form.setFieldsValue({
      guestId: newId
    });
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
        body: JSON.stringify({
          action: 'add_guest_user',
          guestName: values.guestName,
          guestId: values.guestId
        })
      });

      if (!response.ok) {
        throw new Error('Failed to add guest user');
      }

      // Update local data to include the new guest user
      const updatedUsers = [...(data.users || [])];
      updatedUsers.push({
        id: values.guestId,
        name: values.guestName,
        isGuest: true
      });

      onDataChange({
        ...data,
        users: updatedUsers
      });

      onSuccess(`Guest user "${values.guestName}" added successfully!`);
      form.resetFields();
      onClose();
    } catch (error) {
      console.error('Error adding guest user:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <UserOutlined style={{ color: '#1890ff' }} />
          <span>Add Guest User</span>
        </Space>
      }
      open={visible}
      onCancel={handleCancel}
      onOk={handleSave}
      confirmLoading={loading}
      okText="Add Guest"
      cancelText="Cancel"
      width={500}
    >
      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
      >
        <Form.Item
          name="guestName"
          label="Guest Name"
          rules={[
            { required: true, message: 'Please enter a guest name' },
            { min: 2, message: 'Guest name must be at least 2 characters' },
            { max: 50, message: 'Guest name must be less than 50 characters' }
          ]}
          help="Enter a friendly name for the guest user"
        >
          <Input
            placeholder="Enter guest name (e.g., 'John Smith')"
            prefix={<UserOutlined />}
            maxLength={50}
          />
        </Form.Item>

        <Form.Item
          name="guestId"
          label={
            <Space>
              <span>Guest ID</span>
              <Tooltip title="This unique ID will be used to access the guest dashboard">
                <IdcardOutlined style={{ color: '#1890ff' }} />
              </Tooltip>
            </Space>
          }
          rules={[
            { required: true, message: 'Please enter a guest ID' },
            { pattern: /^[a-f0-9-]{36}$/, message: 'Guest ID must be a valid GUID format' }
          ]}
          help="Unique identifier for the guest user (auto-generated)"
        >
          <Input
            placeholder="Guest ID will be auto-generated"
            prefix={<IdcardOutlined />}
            suffix={
              <Button
                type="link"
                size="small"
                onClick={handleGenerateNewId}
                style={{ padding: 0, height: 'auto' }}
              >
                Regenerate
              </Button>
            }
            readOnly={false}
          />
        </Form.Item>

        <div style={{ 
          padding: '12px', 
          backgroundColor: '#f6ffed', 
          border: '1px solid #b7eb8f', 
          borderRadius: '6px',
          marginTop: '16px'
        }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            <strong>Note:</strong> Guest users will appear with a dotted border and can be assigned roles just like regular users. 
            The guest ID can be used to access a temporary guest dashboard.
          </Text>
        </div>
      </Form>
    </Modal>
  );
}
