import { useState, useEffect } from 'preact/hooks';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  Tag,
  Popconfirm,
  Tooltip
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, CodeOutlined } from '@ant-design/icons';
import { RoleEditModal } from './RoleEditModal';

export function RolesManagement({ data, onSuccess, onError, onDataChange }) {
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState({});
  const [editingRole, setEditingRole] = useState(null);
  const [editingRoleData, setEditingRoleData] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Initialize roles from config
  useEffect(() => {
    if (data.config?.roles) {
      setRoles(data.config.roles);
    }
  }, [data.config]);

  const getHAAuth = async () => {
    try {
      const hass = getHassObject();
      if (hass && hass.auth) {
        if (hass.auth.data && hass.auth.data.access_token) {
          return {
            access_token: hass.auth.data.access_token,
            token_type: 'Bearer'
          };
        }
        if (hass.auth.access_token) {
          return {
            access_token: hass.auth.access_token,
            token_type: 'Bearer'
          };
        }
      }
      
      const auth = localStorage.getItem('hassTokens') || sessionStorage.getItem('hassTokens');
      if (auth) {
        const tokens = JSON.parse(auth);
        return {
          access_token: tokens.access_token,
          token_type: 'Bearer'
        };
      }
      
      return null;
    } catch (error) {
      console.error('Auth error:', error);
      return null;
    }
  };

  const getHassObject = () => {
    try {
      const homeAssistantElement = document.querySelector("home-assistant");
      if (homeAssistantElement && homeAssistantElement.hass) {
        return homeAssistantElement.hass;
      }
      if (window.hass) {
        return window.hass;
      }
      if (window.parent && window.parent !== window && window.parent.hass) {
        return window.parent.hass;
      }
      return null;
    } catch (error) {
      console.error('Error getting hass object:', error);
      return null;
    }
  };

  const handleCreateRole = () => {
    setShowCreateModal(true);
  };

  const handleDeleteRole = async (roleName) => {
    if (!confirm(`Are you sure you want to delete the role "${roleName}"?`)) {
      return;
    }

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
          action: 'delete_role',
          roleName: roleName
        })
      });

      if (!response.ok) {
        throw new Error('Failed to delete role');
      }

      // Update local state
      const updatedRoles = { ...roles };
      delete updatedRoles[roleName];
      setRoles(updatedRoles);
      
      // Update parent data
      onDataChange({
        ...data,
        config: {
          ...data.config,
          roles: updatedRoles
        }
      });

      onSuccess(`Role "${roleName}" deleted successfully!`);
    } catch (error) {
      console.error('Error deleting role:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEditRole = (roleName) => {
    const role = roles[roleName];
    if (role) {
      setEditingRole(roleName);
      setEditingRoleData(role);
    }
  };

  const closeRoleModal = () => {
    setEditingRole(null);
    setEditingRoleData(null);
  };

  const closeCreateModal = () => {
    setShowCreateModal(false);
  };

  const handleSaveRole = async (roleData) => {
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
          roleName: editingRole,
          roleConfig: roleData
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update role');
      }

      // Update local state
      const updatedRoles = { ...roles };
      updatedRoles[editingRole] = roleData;
      setRoles(updatedRoles);
      
      // Update parent data
      onDataChange({
        ...data,
        config: {
          ...data.config,
          roles: updatedRoles
        }
      });

      onSuccess(`Role "${editingRole}" updated successfully!`);
      closeRoleModal();
    } catch (error) {
      console.error('Error updating role:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRoleSave = async (roleData) => {
    setLoading(true);
    try {
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }

      // Generate a unique role name
      const roleName = `role_${Date.now()}`;

      const response = await fetch('/api/rbac/config', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'update_role',
          roleName: roleName,
          roleConfig: roleData
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create role');
      }

      // Update local state
      const updatedRoles = { ...roles };
      updatedRoles[roleName] = roleData;
      setRoles(updatedRoles);
      
      // Update parent data
      onDataChange({
        ...data,
        config: {
          ...data.config,
          roles: updatedRoles
        }
      });

      onSuccess(`Role "${roleName}" created successfully!`);
      closeCreateModal();
    } catch (error) {
      console.error('Error creating role:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };


  return (
    <div>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
        Create and manage roles with specific permissions.
      </Typography.Paragraph>
      
      {/* Add Role Button */}
      <Space style={{ marginBottom: 24 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleCreateRole}
          disabled={loading}
        >
          Add Role
        </Button>
      </Space>

      {/* Existing Roles */}
      <Typography.Title level={4}>Existing Roles</Typography.Title>
      
      {Object.keys(roles).length === 0 ? (
        <Typography.Text type="secondary" italic>
          No roles created yet.
        </Typography.Text>
      ) : (
        <Row gutter={[16, 16]}>
          {Object.entries(roles).map(([roleName, role]) => (
            <Col xs={24} sm={12} key={roleName}>
              <Card 
                size="small"
                style={{ height: '100%' }}
                actions={[
                  <Button
                    key="edit"
                    type="link"
                    icon={<EditOutlined />}
                    onClick={() => handleEditRole(roleName)}
                    disabled={loading}
                  >
                    Edit
                  </Button>,
                  <Popconfirm
                    key="delete"
                    title="Are you sure you want to delete this role?"
                    onConfirm={() => handleDeleteRole(roleName)}
                    okText="Yes"
                    cancelText="No"
                  >
                    <Button
                      type="link"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={loading}
                    >
                      Delete
                    </Button>
                  </Popconfirm>
                ]}
              >
                <div style={{ height: '120px', display: 'flex', flexDirection: 'column' }}>
                  <Card.Meta
                    title={roleName}
                    description={role.description || 'No description'}
                  />
                  
                  {/* Show restrictions summary */}
                  <Space wrap style={{ marginTop: 'auto' }}>
                    {role.template && (
                      <Tooltip title={`Template: ${role.template}`}>
                        <Tag color="purple" icon={<CodeOutlined />}>
                          Template
                        </Tag>
                      </Tooltip>
                    )}
                    {Object.keys(role.permissions?.domains || {}).length > 0 && (
                      <Tag color="blue">
                        {Object.keys(role.permissions.domains).length} domains
                      </Tag>
                    )}
                    {Object.keys(role.permissions?.entities || {}).length > 0 && (
                      <Tag color="green">
                        {Object.keys(role.permissions.entities).length} entities
                      </Tag>
                    )}
                  </Space>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Role Edit Modal */}
      <RoleEditModal
        visible={!!editingRole}
        onCancel={closeRoleModal}
        onSave={handleSaveRole}
        roleName={editingRole}
        roleConfig={editingRoleData}
        availableRoles={Object.keys(roles)}
        domains={data.domains}
        entities={data.entities}
        services={data.services}
      />

      {/* Role Create Modal */}
      <RoleEditModal
        visible={showCreateModal}
        onCancel={closeCreateModal}
        onSave={handleCreateRoleSave}
        roleName={null}
        roleConfig={null}
        availableRoles={Object.keys(roles)}
        domains={data.domains}
        entities={data.entities}
        services={data.services}
      />
    </div>
  );
}
