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
import { getHAAuth, makeAuthenticatedRequest } from '../utils/auth';

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

  const handleCreateRole = () => {
    setShowCreateModal(true);
  };

  const handleDeleteRole = async (roleName) => {
    setLoading(true);
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
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

  const handleSaveRole = async (saveData) => {
    setLoading(true);
    try {
      // Extract role name and data
      const { roleName: newRoleName, roleData } = saveData;
      const targetRoleName = newRoleName || editingRole;

      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
        body: JSON.stringify({
          action: 'update_role',
          roleName: targetRoleName,
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

  const handleCreateRoleSave = async (saveData) => {
    setLoading(true);
    try {
      // Extract role name and data from saveData
      const { roleName, roleData } = saveData;

      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
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
                  <div
                    key="edit"
                    style={{
                      padding: '8px 16px',
                      margin: '4px',
                      borderRadius: '4px',
                      transition: 'all 0.2s ease',
                      cursor: 'pointer',
                      backgroundColor: 'transparent',
                      color: '#1890ff',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#1890ff';
                      e.currentTarget.style.color = 'black';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#1890ff';
                    }}
                    onClick={() => handleEditRole(roleName)}
                  >
                    <Button
                      type="link"
                      icon={<EditOutlined />}
                      disabled={loading}
                      style={{ 
                        color: 'inherit',
                        padding: 0,
                        height: 'auto',
                        border: 'none',
                        background: 'transparent',
                      }}
                    >
                      Edit
                    </Button>
                  </div>,
                  <Popconfirm
                    key="delete"
                    title="Are you sure you want to delete this role?"
                    onConfirm={() => handleDeleteRole(roleName)}
                    okText="Yes"
                    cancelText="No"
                  >
                    <div
                      style={{
                        padding: '8px 16px',
                        margin: '4px',
                        borderRadius: '4px',
                        transition: 'all 0.2s ease',
                        cursor: 'pointer',
                        backgroundColor: 'transparent',
                        color: '#ff4d4f',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = '#ff4d4f';
                        e.currentTarget.style.color = 'black';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                        e.currentTarget.style.color = '#ff4d4f';
                      }}
                    >
                      <Button
                        type="link"
                        danger
                        icon={<DeleteOutlined />}
                        disabled={loading}
                        style={{ 
                          color: 'inherit',
                          padding: 0,
                          height: 'auto',
                          border: 'none',
                          background: 'transparent',
                        }}
                      >
                        Delete
                      </Button>
                    </div>
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
                    {role.deny_all && (
                      <Tooltip title="Deny All mode enabled - blocks by default">
                        <Tag color="red">
                          Deny All
                        </Tag>
                      </Tooltip>
                    )}
                    {Object.keys(role.permissions?.domains || {}).length > 0 && (
                      <Tooltip 
                        title={
                          <div>
                            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Domains:</div>
                            {Object.keys(role.permissions.domains).map(domain => (
                              <div key={domain} style={{ fontSize: '12px' }}>• {domain}</div>
                            ))}
                          </div>
                        }
                        placement="top"
                      >
                        <Tag color="blue">
                          {Object.keys(role.permissions.domains).length} domains
                        </Tag>
                      </Tooltip>
                    )}
                    {Object.keys(role.permissions?.entities || {}).length > 0 && (
                      <Tooltip 
                        title={
                          <div>
                            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>Entities:</div>
                            {Object.keys(role.permissions.entities).map(entity => (
                              <div key={entity} style={{ fontSize: '12px' }}>• {entity}</div>
                            ))}
                          </div>
                        }
                        placement="top"
                      >
                        <Tag color="green">
                          {Object.keys(role.permissions.entities).length} entities
                        </Tag>
                      </Tooltip>
                    )}
                  </Space>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* Add Role Button */}
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        onClick={handleCreateRole}
        disabled={loading}
        style={{ width: '100%', marginTop: 16 }}
      >
        Add Role
      </Button>

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
