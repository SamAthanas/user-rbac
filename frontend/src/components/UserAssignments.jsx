import { useState, useEffect } from 'preact/hooks';
import {
  Card,
  Typography,
  Space,
  Row,
  Col,
  Avatar,
  Select,
  Tag,
  Button,
  Divider
} from 'antd';
import { EditOutlined } from '@ant-design/icons';
import { RoleEditModal } from './RoleEditModal';

export function UserAssignments({ data, onSuccess, onError, onDataChange, isDarkMode = false }) {
  const [loading, setLoading] = useState(false);
  const [userRoles, setUserRoles] = useState({});
  const [editingRole, setEditingRole] = useState(null);
  const [editingRoleData, setEditingRoleData] = useState(null);

  // Initialize user roles from config
  useEffect(() => {
    if (data.config?.users) {
      const roles = {};
      Object.entries(data.config.users).forEach(([userId, userConfig]) => {
        roles[userId] = userConfig.role || 'user';
      });
      setUserRoles(roles);
    }
  }, [data.config]);

  // Check if user has an admin role
  const isUserAdmin = (user) => {
    const roleName = userRoles[user.id];
    if (!roleName || !data.config?.roles) return false;
    const role = data.config.roles[roleName];
    return role?.admin === true;
  };

  // Get admin glow styles
  const getAdminGlowStyles = (isAdmin) => {
    if (!isAdmin) return {};
    
    const backgroundColor = isDarkMode ? '#262626' : 'white';
    
    return {
      border: '2px solid transparent',
      background: `linear-gradient(${backgroundColor}, ${backgroundColor}) padding-box, linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57) border-box`,
      animation: 'adminGlow 2s ease-in-out infinite alternate',
      boxShadow: '0 0 20px rgba(255, 107, 107, 0.3)'
    };
  };

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

  const handleRoleChange = async (userId, newRole) => {
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
          action: 'assign_user_role',
          userId: userId,
          roleName: newRole
        })
      });

      if (!response.ok) {
        throw new Error('Failed to assign role');
      }

      // Update local state
      const updatedUserRoles = { ...userRoles, [userId]: newRole };
      setUserRoles(updatedUserRoles);
      
      // Update parent data
      const updatedUsers = { ...data.config?.users || {} };
      if (!updatedUsers[userId]) {
        updatedUsers[userId] = {};
      }
      updatedUsers[userId].role = newRole;
      
      onDataChange({
        ...data,
        config: {
          ...data.config,
          users: updatedUsers
        }
      });

      const user = data.users.find(u => u.id === userId);
      const userName = user ? user.name : userId;
      onSuccess(`Role "${newRole}" assigned to ${userName} successfully!`);
    } catch (error) {
      console.error('Error assigning role:', error);
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
    return roles;
  };

  const getUserDisplayName = (user) => {
    return user.name || user.username || user.id;
  };

  const getUserPicture = (user) => {
    // Use the entity_picture from the person entity if available
    if (user.entity_picture) {
      return user.entity_picture;
    }
    
    // Fallback: construct URL from user ID (for backwards compatibility)
    if (user.id) {
      return `/api/image/serve/${user.id}/512x512`;
    }
    
    return null;
  };

  const handleEditRole = (roleName) => {
    const role = data.config?.roles?.[roleName];
    if (role) {
      setEditingRole(roleName);
      setEditingRoleData(role);
    }
  };

  const closeRoleModal = () => {
    setEditingRole(null);
    setEditingRoleData(null);
  };

  return (
    <div>
      <style>
        {`
          @keyframes adminGlow {
            0% {
              box-shadow: 0 0 20px rgba(255, 107, 107, 0.3);
            }
            100% {
              box-shadow: 0 0 30px rgba(78, 205, 196, 0.5), 0 0 40px rgba(69, 183, 209, 0.3);
            }
          }
        `}
      </style>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
        Assign roles to users to control their access permissions.
      </Typography.Paragraph>
      
      {data.users && data.users.length > 0 ? (
        <Row gutter={[16, 16]}>
          {data.users.map(user => (
            <Col xs={24} sm={12} key={user.id}>
              <Card 
                size="small" 
                style={{ 
                  height: '100%',
                  ...getAdminGlowStyles(isUserAdmin(user))
                }}
              >
                <Space align="center" style={{ width: '100%', height: '80px' }}>
                  {/* User Picture */}
                  <Avatar
                    src={getUserPicture(user)}
                    size={48}
                  >
                    {getUserDisplayName(user).charAt(0).toUpperCase()}
                  </Avatar>
                  
                  {/* User Info */}
                  <Space direction="vertical" style={{ flex: 1 }}>
                    <Typography.Text strong>
                      {getUserDisplayName(user)}
                    </Typography.Text>
                    <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                      ID: {user.id}
                    </Typography.Text>
                  </Space>
                  
                  {/* Role Selector - Right Aligned */}
                  <div style={{ marginLeft: 'auto' }}>
                    <Select
                      value={userRoles[user.id] || 'user'}
                      onChange={(value) => handleRoleChange(user.id, value)}
                      disabled={loading}
                      style={{ minWidth: 120 }}
                      size="small"
                    >
                      {getAvailableRoles().map(role => (
                        <Select.Option key={role} value={role}>
                          {role.charAt(0).toUpperCase() + role.slice(1)}
                        </Select.Option>
                      ))}
                    </Select>
                  </div>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Typography.Text type="secondary" style={{ textAlign: 'center', display: 'block', padding: '40px 0' }}>
          No users found.
        </Typography.Text>
      )}

      {/* Role Edit Modal */}
      <RoleEditModal
        isOpen={!!editingRole}
        onClose={closeRoleModal}
        roleName={editingRole}
        roleData={editingRoleData}
        data={data}
        onSuccess={onSuccess}
        onError={onError}
        onDataChange={onDataChange}
      />
    </div>
  );
}
