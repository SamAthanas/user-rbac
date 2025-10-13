import { useState, useEffect } from 'preact/hooks';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  Select
} from 'antd';
import { EditOutlined } from '@ant-design/icons';
import { makeAuthenticatedRequest, getHAAuth } from '../utils/auth';
import { RoleEditModal } from './RoleEditModal';

export function DefaultRestrictions({ data, onSuccess, onError, onDataChange }) {
  const [loading, setLoading] = useState(false);
  const [defaultRole, setDefaultRole] = useState('none');
  const [editingRole, setEditingRole] = useState(null);
  const [editingRoleData, setEditingRoleData] = useState(null);

  // Initialize default role from config
  useEffect(() => {
    if (data.config?.default_role !== undefined) {
      setDefaultRole(data.config.default_role || 'none');
    }
  }, [data.config]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
        body: JSON.stringify({
          action: 'update_default_role',
          default_role: defaultRole
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save default role');
      }

      onSuccess('Default role saved successfully!');
    } catch (error) {
      console.error('Error saving default role:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const getAvailableRoles = () => {
    const roles = Object.keys(data.config?.roles || {});
    // Add default roles if they don't exist
    if (!roles.includes('admin')) roles.unshift('admin');
    if (!roles.includes('user')) roles.push('user');
    if (!roles.includes('guest')) roles.push('guest');
    roles.unshift('none');
    return roles;
  };

  const handleEditRole = () => {
    if (defaultRole && defaultRole !== 'none') {
      const role = data.config?.roles?.[defaultRole];
      if (role) {
        setEditingRole(defaultRole);
        setEditingRoleData(role);
      }
    }
  };

  const closeRoleModal = () => {
    setEditingRole(null);
    setEditingRoleData(null);
  };

  const handleSaveRole = async (saveData) => {
    setLoading(true);
    try {
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }

      const response = await fetch('/api/rbac/config', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'update_role',
          roleName: saveData.roleName,
          roleData: saveData.roleData
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save role');
      }

      // Update local data
      const updatedConfig = { ...data.config };
      if (!updatedConfig.roles) {
        updatedConfig.roles = {};
      }
      updatedConfig.roles[saveData.roleName] = saveData.roleData;
      
      onDataChange({
        ...data,
        config: updatedConfig
      });

      closeRoleModal();
      onSuccess(`Role "${saveData.roleName}" updated successfully!`);
    } catch (error) {
      console.error('Error saving role:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <div>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
        Configure the default role that will be applied to users who have no specific role assigned or have the "Default" role assigned.
      </Typography.Paragraph>
      
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
            Default Role
          </Typography.Text>
          <Space.Compact style={{ width: '100%' }}>
            <Select
              value={defaultRole}
              onChange={setDefaultRole}
              placeholder="Select default role (None = no restrictions)"
              style={{ flex: 1 }}
              allowClear
              disabled={loading}
            >
              {getAvailableRoles().map(role => (
                <Select.Option key={role} value={role}>
                  {role === 'none' ? 'None' : role.charAt(0).toUpperCase() + role.slice(1)}
                </Select.Option>
              ))}
            </Select>
            {defaultRole && defaultRole !== 'none' && (
              <Button
                icon={<EditOutlined />}
                onClick={handleEditRole}
                disabled={loading}
                title={`Edit ${defaultRole.charAt(0).toUpperCase() + defaultRole.slice(1)} role`}
              />
            )}
          </Space.Compact>
          <Typography.Text type="secondary" style={{ fontSize: '12px', display: 'block', marginTop: 4 }}>
            Users without a specific role or with "Default" role will use this role's permissions. Select "None" to allow all access by default.
          </Typography.Text>
        </Col>
      </Row>
      
      <Space style={{ justifyContent: 'flex-end', display: 'flex', width: '100%', marginTop: 24 }}>
        <Button
          type="primary"
          onClick={handleSave}
          disabled={loading}
          loading={loading}
          size="large"
        >
          Save Default Role
        </Button>
      </Space>

      {/* Role Edit Modal */}
      <RoleEditModal
        visible={!!editingRole}
        onCancel={closeRoleModal}
        onSave={handleSaveRole}
        roleName={editingRole}
        roleConfig={editingRoleData}
        availableRoles={Object.keys(data.config?.roles || {})}
        domains={data.domains}
        entities={data.entities}
        services={data.services}
      />
    </div>
  );
}
