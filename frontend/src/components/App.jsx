import { useState, useEffect } from 'preact/hooks';
import { ConfigProvider, Layout, notification, Collapse, Alert, Button, Card, Switch, Tooltip, Typography } from 'antd';
import { Header } from './Header';
import { DefaultRestrictions } from './DefaultRestrictions';
import { RolesManagement } from './RolesManagement';
import { UserAssignments } from './UserAssignments';
import { Loading } from './Loading';
import { ExclamationCircleOutlined, SettingOutlined, ReloadOutlined } from '@ant-design/icons';

export function App() {
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [integrationConfigured, setIntegrationConfigured] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [enabled, setEnabled] = useState(true);
  const [showNotifications, setShowNotifications] = useState(true);
  const [sendEvent, setSendEvent] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sensors, setSensors] = useState({
    last_rejection: null,
    last_user_rejected: null
  });
  const [data, setData] = useState({
    users: [],
    domains: [],
    entities: [],
    services: [],
    config: null
  });

  // Collapsible sections state
  const [collapsedSections, setCollapsedSections] = useState({
    settings: false,
    defaultRestrictions: false,
    rolesManagement: false,
    userAssignments: false
  });

  // Ant Design theme configuration
  const theme = {
    token: {
      colorPrimary: '#1890ff',
      borderRadius: 6,
    },
  };

  useEffect(() => {
    loadData();
    loadCollapsedState();
  }, []);

  const loadCollapsedState = () => {
    try {
      const saved = localStorage.getItem('rbac-collapsed-sections');
      if (saved) {
        const savedState = JSON.parse(saved);
        // Merge with default state to ensure all keys exist
        const defaultState = {
          settings: false,
          defaultRestrictions: false,
          rolesManagement: false,
          userAssignments: false
        };
        setCollapsedSections({ ...defaultState, ...savedState });
      }
    } catch (error) {
      console.warn('Could not load collapsed state from localStorage:', error);
    }
  };

  const saveCollapsedState = (newState) => {
    try {
      localStorage.setItem('rbac-collapsed-sections', JSON.stringify(newState));
    } catch (error) {
      console.warn('Could not save collapsed state to localStorage:', error);
    }
  };

  const handleSectionChange = (key, isCollapsed) => {
    const newState = { ...collapsedSections, [key]: isCollapsed };
    setCollapsedSections(newState);
    saveCollapsedState(newState);
  };

  const loadData = async (isManualReload = false) => {
    try {
      // Clear any previous API errors
      setApiError(null);
      
      if (isManualReload) {
        setReloading(true);
      } else {
        setLoading(true);
      }
      console.log('Starting to load data...');

      const auth = await getHAAuth();
      console.log('Auth result:', auth);
      
      if (!auth) {
        setIsAuthenticated(false);
        throw new Error('Not authenticated with Home Assistant');
      }
      
      setIsAuthenticated(true);

      // Fetch current user
      const userData = await fetchCurrentUser(auth);
      setCurrentUser(userData);

      // Fetch sensors
      const sensorsData = await fetchSensors(auth);
      if (sensorsData) {
        setSensors(sensorsData);
      }

      console.log('Making API calls...');
      const [usersRes, domainsRes, entitiesRes, servicesRes, configRes] = await Promise.all([
        fetch('/api/rbac/users', {
          headers: { 'Authorization': `Bearer ${auth.access_token}` }
        }),
        fetch('/api/rbac/domains', {
          headers: { 'Authorization': `Bearer ${auth.access_token}` }
        }),
        fetch('/api/rbac/entities', {
          headers: { 'Authorization': `Bearer ${auth.access_token}` }
        }),
        fetch('/api/rbac/services', {
          headers: { 'Authorization': `Bearer ${auth.access_token}` }
        }),
        fetch('/api/rbac/config', {
          headers: { 'Authorization': `Bearer ${auth.access_token}` }
        })
      ]);

      console.log('API responses:', { usersRes, domainsRes, entitiesRes, servicesRes, configRes });

      // Check for admin access denied (403)
      if (usersRes.status === 403 || domainsRes.status === 403 || entitiesRes.status === 403 || 
          servicesRes.status === 403 || configRes.status === 403) {
        const errorData = await configRes.json();
        
        // Set admin access denied state
        setApiError('Admin access required');
        
        // Show admin access denied notification
        notification.error({
          message: 'Access Denied',
          description: 'Only administrators can access RBAC configuration. You will be redirected to the main page.',
          placement: 'topRight',
          duration: 5,
        });
        
        // Redirect to Home Assistant main page after 5 seconds
        setTimeout(() => {
          window.location.href = errorData.redirect_url || '/';
        }, 5000);
        return;
      }

      // Check if any API call returns 404 or indicates integration not configured
      if (usersRes.status === 404 || domainsRes.status === 404 || entitiesRes.status === 404 || 
          servicesRes.status === 404 || configRes.status === 404) {
        setIntegrationConfigured(false);
        if (isManualReload) {
          setReloading(false);
        } else {
          setLoading(false);
        }
        return;
      }

      if (!usersRes.ok || !domainsRes.ok || !entitiesRes.ok || !servicesRes.ok || !configRes.ok) {
        throw new Error('Failed to load data from API');
      }

      const [users, domains, entities, services, config] = await Promise.all([
        usersRes.json(),
        domainsRes.json(),
        entitiesRes.json(),
        servicesRes.json(),
        configRes.json()
      ]);

      console.log('Loaded data:', { users, domains, entities, services, config });
      setData({ users, domains, entities, services, config });
      setIntegrationConfigured(true);
      
      // Load enabled state from config
      if (config && config.enabled !== undefined) {
        setEnabled(config.enabled);
      }
      
      // Load other settings from config
      if (config) {
        setShowNotifications(config.show_notifications !== undefined ? config.show_notifications : true);
        setSendEvent(config.send_event !== undefined ? config.send_event : false);
      }
      
      // Show success notification for manual reload
      if (isManualReload) {
        notification.success({
          message: 'Data Reloaded',
          description: 'RBAC configuration has been refreshed successfully.',
          placement: 'topRight',
          duration: 2,
        });
      }
    } catch (err) {
      console.error('Error loading data:', err);
      
      // Check if the error indicates integration not configured
      if (err.message.includes('404') || err.message.includes('Not Found')) {
        setIntegrationConfigured(false);
      } else {
        // Set API error state for display
        setApiError(err.message);
        notification.error({
          message: 'Error Loading Data',
          description: err.message,
          placement: 'topRight',
          duration: 5,
        });
      }
    } finally {
      if (isManualReload) {
        setReloading(false);
      } else {
        setLoading(false);
      }
    }
  };

  const handleManualReload = () => {
    loadData(true);
  };

  const handleEnabledToggle = async (checked) => {
    try {
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }

      const response = await fetch('/api/rbac/config', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action: 'update_settings',
          enabled: checked
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update enabled state');
      }

      setEnabled(checked);
      notification.success({
        message: 'Settings Updated',
        description: `RBAC is now ${checked ? 'enabled' : 'disabled'}`,
        placement: 'topRight',
        duration: 3,
      });
    } catch (error) {
      console.error('Error updating enabled state:', error);
      notification.error({
        message: 'Error',
        description: error.message,
        placement: 'topRight',
        duration: 5,
      });
    }
  };

  const handleSettingsUpdate = async (settings) => {
    try {
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }

      const response = await fetch('/api/rbac/config', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          action: 'update_settings',
          ...settings  // Spread settings at root level
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update settings');
      }

      // Update local state
      if (settings.show_notifications !== undefined) {
        setShowNotifications(settings.show_notifications);
      }
      if (settings.send_event !== undefined) {
        setSendEvent(settings.send_event);
      }

      notification.success({
        message: 'Settings Updated',
        description: 'RBAC settings have been updated',
        placement: 'topRight',
        duration: 3,
      });
    } catch (error) {
      console.error('Error updating settings:', error);
      notification.error({
        message: 'Error',
        description: error.message,
        placement: 'topRight',
        duration: 5,
      });
    }
  };

  const getHAAuth = async () => {
    try {
      // Try to get from localStorage (if available)
      const auth = localStorage.getItem('hassTokens');
      if (auth) {
        const tokens = JSON.parse(auth);
        return {
          access_token: tokens.access_token,
          token_type: 'Bearer'
        };
      }
      
      // Try to get from sessionStorage
      const sessionAuth = sessionStorage.getItem('hassTokens');
      if (sessionAuth) {
        const tokens = JSON.parse(sessionAuth);
        return {
          access_token: tokens.access_token,
          token_type: 'Bearer'
        };
      }
      
      // Fallback: try to get auth from the current page context
      const response = await fetch('/auth/token');
      if (!response.ok) {
        throw new Error('Not authenticated');
      }
      return await response.json();
    } catch (error) {
      console.error('Auth error:', error);
      return null;
    }
  };

  const fetchCurrentUser = async (auth) => {
    try {
      const response = await fetch('/api/rbac/current-user', {
        headers: { 'Authorization': `Bearer ${auth.access_token}` }
      });
      
      if (response.ok) {
        const userData = await response.json();
        console.log('Current user data received:', userData);
        return userData;
      }
      return null;
    } catch (error) {
      console.error('Error fetching current user:', error);
      return null;
    }
  };

  const fetchSensors = async (auth) => {
    try {
      const response = await fetch('/api/rbac/sensors', {
        headers: { 'Authorization': `Bearer ${auth.access_token}` }
      });
      
      if (response.ok) {
        const sensorsData = await response.json();
        return sensorsData;
      }
      return null;
    } catch (error) {
      console.error('Error fetching sensors:', error);
      return null;
    }
  };

  const showSuccess = (message) => {
    notification.success({
      message: 'Success',
      description: message,
      placement: 'topRight',
      duration: 3,
    });
    
    // Auto-reload data after successful API operations
    setTimeout(() => {
      loadData(true);
    }, 500); // Small delay to let the user see the success message
  };

  const showError = (message) => {
    notification.error({
      message: 'Error',
      description: message,
      placement: 'topRight',
      duration: 5,
    });
  };

  if (loading) {
    return <Loading />;
  }

  // Show authentication required banner if not logged in
  if (!isAuthenticated) {
    return (
      <ConfigProvider theme={theme}>
        <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
          <Layout.Content style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
            <Header currentUser={currentUser} />
            
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              minHeight: '60vh',
              flexDirection: 'column',
              gap: '24px'
            }}>
              <Alert
                message={<div style={{ textAlign: 'center' }}>Authentication Required</div>}
                description={
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ marginBottom: '24px' }}>
                      You must be logged into Home Assistant to access RBAC configuration.
                    </p>
                    <Button 
                      type="primary" 
                      onClick={() => window.location.href = '/'}
                      style={{ marginRight: '12px' }}
                    >
                      Go to Home Assistant Login
                    </Button>
                    <Button 
                      onClick={() => loadData()}
                      icon={<ReloadOutlined />}
                    >
                      Retry Authentication
                    </Button>
                  </div>
                }
                type="warning"
                showIcon
                style={{ maxWidth: '500px', width: '100%' }}
              />
            </div>
          </Layout.Content>
        </Layout>
      </ConfigProvider>
    );
  }

  // Show integration configuration error if not configured
  if (!integrationConfigured) {
    return (
      <ConfigProvider theme={theme}>
        <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
          <Layout.Content style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
            <Header currentUser={currentUser} />
            
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              minHeight: '60vh',
              flexDirection: 'column',
              gap: '24px'
            }}>
              <Alert
                message={<div style={{ textAlign: 'center' }}>RBAC Integration Required</div>}
                description={
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ marginBottom: '24px' }}>
                      Please configure the RBAC integration first.
                    </p>
                    <Button 
                      type="primary" 
                      icon={<SettingOutlined />}
                      size="large"
                      onClick={() => {
                        // Get the current domain from the URL
                        const domain = window.location.hostname;
                        const protocol = window.location.protocol;
                        const port = window.location.port ? `:${window.location.port}` : '';
                        const integrationUrl = `${protocol}//${domain}${port}/config/integrations/integration/rbac`;
                        window.open(integrationUrl, '_blank');
                      }}
                    >
                      Configure Integration
                    </Button>
                  </div>
                }
                type="error"
                icon={<ExclamationCircleOutlined />}
                showIcon
                style={{ maxWidth: '500px', width: '100%' }}
              />
            </div>
          </Layout.Content>
        </Layout>
      </ConfigProvider>
    );
  }

  // Show API error if there's a loading failure
  if (apiError) {
    const isAdminError = apiError === 'Admin access required';
    
    return (
      <ConfigProvider theme={theme}>
        <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
          <Layout.Content style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
            <Header currentUser={currentUser} />
            
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center', 
              minHeight: '60vh',
              flexDirection: 'column',
              gap: '24px'
            }}>
              <Alert
                message={<div style={{ textAlign: 'center' }}>
                  {isAdminError ? 'Admin Access Required' : 'Failed to Load RBAC Data'}
                </div>}
                description={
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ marginBottom: '24px' }}>
                      {isAdminError 
                        ? 'Only administrators can access RBAC configuration. Please contact your system administrator or log in with an admin account.'
                        : apiError
                      }
                    </p>
                    {isAdminError ? (
                      <Button 
                        type="primary" 
                        onClick={() => window.location.href = '/'}
                        style={{ marginRight: '12px' }}
                      >
                        Go to Home Assistant
                      </Button>
                    ) : (
                      <Button 
                        type="primary" 
                        icon={<ReloadOutlined />}
                        size="large"
                        onClick={() => loadData(true)}
                      >
                        Retry Loading
                      </Button>
                    )}
                  </div>
                }
                type={isAdminError ? "error" : "error"}
                icon={<ExclamationCircleOutlined />}
                showIcon
                style={{ maxWidth: '500px', width: '100%' }}
              />
            </div>
          </Layout.Content>
        </Layout>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={theme}>
      <style>
        {`
          .ant-collapse-header {
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
            background: white !important;
            border-bottom: 1px solid #f0f0f0 !important;
          }
        `}
      </style>
      <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
        <Layout.Content style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
          <Header currentUser={currentUser} />
          
          <Collapse 
            activeKey={Object.keys(collapsedSections).filter(key => !collapsedSections[key])}
            onChange={(keys) => {
              const newState = {};
              Object.keys(collapsedSections).forEach(key => {
                newState[key] = !keys.includes(key);
              });
              setCollapsedSections(newState);
              saveCollapsedState(newState);
            }}
            style={{ marginBottom: 24 }}
            expandIconPosition="right"
          >
            <Collapse.Panel 
              header={
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                  <span>Settings</span>
                  <Button
                    type="primary"
                    icon={<ReloadOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleManualReload();
                    }}
                    loading={reloading}
                    size="small"
                    style={{ marginLeft: '16px' }}
                  >
                    Reload
                  </Button>
                </div>
              }
              key="settings"
            >
              <Card size="small">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={enabled ? "RBAC is currently enabled" : "RBAC is currently disabled"}>
                      <Switch
                        checked={enabled}
                        onChange={handleEnabledToggle}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <span style={{ color: '#666' }}>
                      RBAC is {enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={showNotifications ? "Notifications are enabled" : "Notifications are disabled"}>
                      <Switch
                        checked={showNotifications}
                        onChange={(checked) => handleSettingsUpdate({ show_notifications: checked })}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <span style={{ color: '#666', fontSize: '14px' }}>
                      Show Notifications
                    </span>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={sendEvent ? "Events are enabled" : "Events are disabled"}>
                      <Switch
                        checked={sendEvent}
                        onChange={(checked) => handleSettingsUpdate({ send_event: checked })}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <span style={{ color: '#666', fontSize: '14px' }}>
                      Send Event
                    </span>
                    {sendEvent && (
                      <span style={{ fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
                        Event: rbac_access_denied
                      </span>
                    )}
                  </div>
                </div>
              </Card>
              
              {/* RBAC Status Sensors */}
              <Card size="small" style={{ marginTop: '16px' }}>
                <Typography.Title level={5} style={{ marginBottom: '16px' }}>
                  RBAC Status Sensors
                </Typography.Title>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                  <div 
                    className="rbac-sensor-card"
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '8px', 
                      padding: '12px', 
                      background: '#f5f5f5', 
                      borderRadius: '8px',
                      border: '2px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    <span style={{ fontSize: '16px' }}>⏰</span>
                    <div>
                      <Typography.Text strong>Last Rejection</Typography.Text>
                      <br />
                      <Typography.Text type="secondary">
                        {sensors.last_rejection?.state || 'Never'}
                      </Typography.Text>
                    </div>
                  </div>
                  
                  <div 
                    className="rbac-sensor-card"
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '8px', 
                      padding: '12px', 
                      background: '#f5f5f5', 
                      borderRadius: '8px',
                      border: '2px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    <span style={{ fontSize: '16px' }}>👤</span>
                    <div>
                      <Typography.Text strong>Last User Rejected</Typography.Text>
                      <br />
                      <Typography.Text type="secondary">
                        {sensors.last_user_rejected?.state || 'None'}
                      </Typography.Text>
                    </div>
                  </div>
                  
                  <div 
                    className="rbac-sensor-card"
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '8px', 
                      padding: '12px', 
                      background: '#f5f5f5', 
                      borderRadius: '8px',
                      border: '2px solid transparent',
                      cursor: 'pointer',
                      transition: 'all 0.3s ease'
                    }}
                  >
                    <span style={{ fontSize: '16px' }}>🌐</span>
                    <div>
                      <Typography.Text strong>Config URL</Typography.Text>
                      <br />
                      <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                        /local/community/rbac/config.html
                      </Typography.Text>
                    </div>
                  </div>
                </div>
              </Card>
              
              <style>
                {`
                  .rbac-sensor-card:hover {
                    background: linear-gradient(135deg, #f5f5f5 0%, #e8f4fd 100%) !important;
                    border: 2px solid transparent !important;
                    background-clip: padding-box !important;
                    box-shadow: 0 0 20px rgba(24, 144, 255, 0.3) !important;
                    transform: translateY(-2px) !important;
                  }
                  
                  .rbac-sensor-card:hover::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    border-radius: 8px;
                    padding: 2px;
                    background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4, #feca57);
                    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                    mask-composite: exclude;
                    z-index: -1;
                  }
                `}
              </style>
            </Collapse.Panel>
            <Collapse.Panel 
              header="Default Restrictions" 
              key="defaultRestrictions"
            >
              <DefaultRestrictions 
                data={data} 
                onSuccess={showSuccess}
                onError={showError}
              />
            </Collapse.Panel>
            
            <Collapse.Panel 
              header="Roles Management" 
              key="rolesManagement"
            >
              <RolesManagement 
                data={data} 
                onSuccess={showSuccess}
                onError={showError}
                onDataChange={setData}
              />
            </Collapse.Panel>
            
            <Collapse.Panel 
              header="User Role Assignments" 
              key="userAssignments"
            >
              <UserAssignments 
                data={data} 
                onSuccess={showSuccess}
                onError={showError}
                onDataChange={setData}
              />
            </Collapse.Panel>
          </Collapse>
        </Layout.Content>
      </Layout>
    </ConfigProvider>
  );
}
