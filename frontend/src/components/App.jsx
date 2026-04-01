import { useState, useEffect } from 'preact/hooks';
import { ConfigProvider, Layout, notification, Collapse, Alert, Button, Card, Switch, Tooltip, Typography, theme } from 'antd';
import { Header } from './Header';
import { DefaultRestrictions } from './DefaultRestrictions';
import { RolesManagement } from './RolesManagement';
import { UserAssignments } from './UserAssignments';
import { DenyLogModal } from './DenyLogModal';
import { YamlEditorModal } from './YamlEditorModal';
import { Loading } from './Loading';
import { ExclamationCircleOutlined, SettingOutlined, ReloadOutlined } from '@ant-design/icons';
import { initializeTheme, applyTheme, saveTheme } from '../utils/theme';
import { getHAAuth, makeAuthenticatedRequest } from '../utils/auth';

export function App() {
  const [loading, setLoading] = useState(true);
  const [reloading, setReloading] = useState(false);
  const [integrationConfigured, setIntegrationConfigured] = useState(true);
  const [apiError, setApiError] = useState(null);
  const [enabled, setEnabled] = useState(true);
  const [showNotifications, setShowNotifications] = useState(true);
  const [sendEvent, setSendEvent] = useState(false);
  const [frontendBlocking, setFrontendBlocking] = useState(false);
  const [logDenyList, setLogDenyList] = useState(false);
  const [allowChainedActions, setAllowChainedActions] = useState(false);
  const [denyLogModalVisible, setDenyLogModalVisible] = useState(false);
  const [yamlEditorModalVisible, setYamlEditorModalVisible] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
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
  const antdTheme = {
    algorithm: isDarkMode ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: {
      colorPrimary: '#1890ff',
      borderRadius: 6,
    },
  };

  useEffect(() => {
    loadData();
    loadCollapsedState();
    loadTheme();
  }, []);

  const loadTheme = () => {
    try {
      const themeMode = initializeTheme();
      setIsDarkMode(themeMode);
    } catch (error) {
      console.warn('Could not load theme:', error);
    }
  };

  const handleThemeToggle = () => {
    const newTheme = !isDarkMode;
    setIsDarkMode(newTheme);
    applyTheme(newTheme);
    saveTheme(newTheme);
  };

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
      const auth = await getHAAuth();
      
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

      const [usersRes, domainsRes, entitiesRes, servicesRes, configRes] = await Promise.all([
        makeAuthenticatedRequest('/api/rbac/users'),
        makeAuthenticatedRequest('/api/rbac/domains'),
        makeAuthenticatedRequest('/api/rbac/entities'),
        makeAuthenticatedRequest('/api/rbac/services'),
        makeAuthenticatedRequest('/api/rbac/config')
      ]);

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
          placement: 'bottomRight',
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
        setFrontendBlocking(config.frontend_blocking_enabled !== undefined ? config.frontend_blocking_enabled : false);
        setLogDenyList(config.log_deny_list !== undefined ? config.log_deny_list : false);
        setAllowChainedActions(config.allow_chained_actions !== undefined ? config.allow_chained_actions : false);
      }
      
      // Show success notification for manual reload
      if (isManualReload) {
        notification.success({
          message: 'Data Reloaded',
          description: 'RBAC configuration has been refreshed successfully.',
          placement: 'bottomRight',
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
          placement: 'bottomRight',
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
      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
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
        placement: 'bottomRight',
        duration: 3,
      });
    } catch (error) {
      console.error('Error updating enabled state:', error);
      notification.error({
        message: 'Error',
        description: error.message,
        placement: 'bottomRight',
        duration: 5,
      });
    }
  };

  const handleSettingsUpdate = async (settings) => {
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/config', {
        method: 'POST',
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
      if (settings.frontend_blocking_enabled !== undefined) {
        setFrontendBlocking(settings.frontend_blocking_enabled);
      }
      if (settings.log_deny_list !== undefined) {
        setLogDenyList(settings.log_deny_list);
      }
      if (settings.allow_chained_actions !== undefined) {
        setAllowChainedActions(settings.allow_chained_actions);
      }

      notification.success({
        message: 'Settings Updated',
        description: 'RBAC settings have been updated',
        placement: 'bottomRight',
        duration: 3,
      });
    } catch (error) {
      console.error('Error updating settings:', error);
      notification.error({
        message: 'Error',
        description: error.message,
        placement: 'bottomRight',
        duration: 5,
      });
    }
  };

  const fetchCurrentUser = async (auth) => {
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/current-user');
      
      if (response.ok) {
        const userData = await response.json();
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
      const response = await makeAuthenticatedRequest('/api/rbac/sensors');
      
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
      placement: 'bottomRight',
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
      placement: 'bottomRight',
      duration: 5,
    });
  };

  if (loading) {
    return <Loading />;
  }

  // Show authentication required banner if not logged in
  if (!isAuthenticated) {
    return (
      <ConfigProvider theme={antdTheme}>
        <Layout style={{ minHeight: '100vh', background: isDarkMode ? '#141414' : '#f0f2f5' }}>
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
      <ConfigProvider theme={antdTheme}>
        <Layout style={{ minHeight: '100vh', background: isDarkMode ? '#141414' : '#f0f2f5' }}>
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
      <ConfigProvider theme={antdTheme}>
        <Layout style={{ minHeight: '100vh', background: isDarkMode ? '#141414' : '#f0f2f5' }}>
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
    <ConfigProvider theme={antdTheme}>
      <style>
        {`
          /* Dark theme background styles */
          html.dark-theme {
            background: #141414 !important;
          }
          
          html.dark-theme body {
            background: #141414 !important;
            color: #ffffff !important;
          }
          
          html.dark-theme .ant-layout {
            background: #141414 !important;
          }
          
          html.dark-theme .ant-layout-content {
            background: #141414 !important;
          }
          
          /* Custom elements dark theme */
          html.dark-theme .rbac-sensor-card {
            background: #262626 !important;
            color: #ffffff !important;
          }
          
          html.dark-theme .rbac-sensor-card:hover {
            background: linear-gradient(135deg, #303030 0%, #262626 100%) !important;
            border: 2px solid transparent !important;
            background-clip: padding-box !important;
            box-shadow: 0 0 20px rgba(24, 144, 255, 0.3) !important;
            transform: translateY(-2px) !important;
          }
          
          /* Textarea and template editor dark theme */
          html.dark-theme .ant-input[type="textarea"] {
            background: #262626 !important;
            color: #ffffff !important;
            border-color: #434343 !important;
          }
          
          html.dark-theme .ant-input[type="textarea"]:focus {
            background: #262626 !important;
            color: #ffffff !important;
            border-color: #1890ff !important;
            box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2) !important;
          }
          
          html.dark-theme .ant-input[type="textarea"]::placeholder {
            color: #8c8c8c !important;
          }
          
          html.dark-theme textarea.ant-input {
            background: #262626 !important;
            color: #ffffff !important;
            border-color: #434343 !important;
          }
          
          html.dark-theme textarea.ant-input:focus {
            background: #262626 !important;
            color: #ffffff !important;
            border-color: #1890ff !important;
            box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2) !important;
          }
          
          html.dark-theme textarea.ant-input::placeholder {
            color: #8c8c8c !important;
          }
          
          /* CodeMirror template editor dark theme */
          html.dark-theme .cm-editor {
            background: #262626 !important;
            color: #ffffff !important;
          }
          
          html.dark-theme .cm-scroller {
            background: #262626 !important;
            color: #ffffff !important;
          }
          
          html.dark-theme .cm-content {
            background: #262626 !important;
            color: #ffffff !important;
          }
          
          html.dark-theme .cm-focused {
            background: #262626 !important;
          }
          
          html.dark-theme .cm-editor .cm-line {
            color: #ffffff !important;
          }
          
          html.dark-theme .cm-editor .cm-cursor {
            border-left-color: #ffffff !important;
          }
          
          html.dark-theme .cm-editor .cm-selectionBackground {
            background: #434343 !important;
          }
          
          html.dark-theme .cm-gutters {
            background: #1f1f1f !important;
            border-right: 1px solid #434343 !important;
          }
          
          html.dark-theme .cm-lineNumbers .cm-gutterElement {
            color: #8c8c8c !important;
          }
          
          /* Theme toggle button hover styles */
          html.dark-theme .ant-btn-icon-only:hover .anticon-sun {
            color: #000000 !important;
          }
          
          /* Theme toggle icon animation */
          @keyframes themeToggleSpin {
            0% {
              transform: rotate(0deg);
            }
            100% {
              transform: rotate(360deg);
            }
          }
          
          .theme-toggle-spin {
            animation: themeToggleSpin 1s ease-out;
          }
          
          .ant-collapse-header {
            position: sticky !important;
            top: 0 !important;
            z-index: 100 !important;
          }
          
          /* Sticky header background for dark theme */
          html.dark-theme .ant-collapse-header {
            background: #262626 !important;
            border-bottom: 1px solid #434343 !important;
          }
          
          html.dark-theme .ant-collapse-header:hover {
            background: #303030 !important;
          }
          
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
          
          @keyframes bannerSlideIn {
            0% {
              opacity: 0;
              transform: translateY(-20px) scale(0.95);
              filter: blur(2px);
            }
            50% {
              opacity: 0.7;
              transform: translateY(-5px) scale(0.98);
              filter: blur(1px);
            }
            100% {
              opacity: 1;
              transform: translateY(0) scale(1);
              filter: blur(0px);
            }
          }
        `}
      </style>
      <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
        <Layout.Content style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
          <Header 
            currentUser={currentUser} 
            isDarkMode={isDarkMode}
            onThemeToggle={handleThemeToggle}
          />
          
          {/* RBAC Disabled Warning Banner */}
          {!enabled && (
            <Alert
              message="RBAC is Disabled"
              description={
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Role-based access control is currently disabled. All users have full access to all services and entities.</span>
                  <Button
                    type="primary"
                    onClick={() => handleEnabledToggle(true)}
                    style={{ marginLeft: '16px' }}
                  >
                    Enable RBAC
                  </Button>
                </div>
              }
              type="warning"
              showIcon
              style={{ 
                marginBottom: '24px',
                animation: 'bannerSlideIn 0.5s ease-out',
                transform: 'translateY(0)',
                opacity: 1
              }}
            />
          )}
          
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
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <Tooltip title="Edit the access_control.yaml configuration file directly">
                      <Button
                        type="default"
                        icon={<ExclamationCircleOutlined />}
                        onClick={(e) => {
                          e.stopPropagation();
                          setYamlEditorModalVisible(true);
                        }}
                        size="small"
                        style={{ 
                          borderColor: '#1890ff',
                          color: '#1890ff',
                          backgroundColor: 'transparent'
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#1890ff';
                          e.currentTarget.style.color = 'white';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = 'transparent';
                          e.currentTarget.style.color = '#1890ff';
                        }}
                      >
                        Edit YAML
                      </Button>
                    </Tooltip>
                    <Button
                      type="primary"
                      icon={<ReloadOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleManualReload();
                      }}
                      loading={reloading}
                      size="small"
                    >
                      Reload
                    </Button>
                  </div>
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
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={frontendBlocking ? "Frontend blocking is enabled" : "Frontend blocking is disabled"}>
                      <Switch
                        checked={frontendBlocking}
                        onChange={(checked) => handleSettingsUpdate({ frontend_blocking_enabled: checked })}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <Tooltip title="Restricts the ha-quick-bar to only allowed entities">
                      <span style={{ color: '#666', fontSize: '14px', cursor: 'help' }}>
                        Frontend Blocking
                      </span>
                    </Tooltip>
                    {frontendBlocking && (
                      <span style={{ fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
                        Add frontend script to /api/rbac/static/rbac.js
                      </span>
                    )}
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={logDenyList ? "Deny list logging is enabled" : "Deny list logging is disabled"}>
                      <Switch
                        checked={logDenyList}
                        onChange={(checked) => handleSettingsUpdate({ log_deny_list: checked })}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <Tooltip title="Logs all access denials to deny_list.log file">
                      <span style={{ color: '#666', fontSize: '14px', cursor: 'help' }}>
                        Deny List Logging
                      </span>
                    </Tooltip>
                    {logDenyList && (
                      <Button
                        size="small"
                        type="link"
                        onClick={() => setDenyLogModalVisible(true)}
                        style={{ padding: '0 4px', height: 'auto', fontSize: '12px' }}
                      >
                        View Logs
                      </Button>
                    )}
                    {logDenyList && (
                      <span style={{ fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
                        File: custom_components/rbac/deny_list.log
                      </span>
                    )}
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Tooltip title={allowChainedActions ? "Chained actions are allowed" : "Chained actions are blocked"}>
                      <Switch
                        checked={allowChainedActions}
                        onChange={(checked) => handleSettingsUpdate({ allow_chained_actions: checked })}
                        checkedChildren="On"
                        unCheckedChildren="Off"
                      />
                    </Tooltip>
                    <Tooltip title="Allow actions within scripts/automations to run if the parent script/automation was allowed">
                      <span style={{ color: '#666', fontSize: '14px', cursor: 'help' }}>
                        Allow Chained Actions
                      </span>
                    </Tooltip>
                    {allowChainedActions && (
                      <span style={{ fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
                        Actions in allowed scripts/automations bypass RBAC
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
                        /api/rbac/static/config.html
                      </Typography.Text>
                    </div>
                  </div>
                </div>
              </Card>
              
            </Collapse.Panel>
            <Collapse.Panel 
              header="Default Restrictions" 
              key="defaultRestrictions"
            >
              <DefaultRestrictions 
                data={data} 
                onSuccess={showSuccess}
                onError={showError}
                onDataChange={setData}
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
                isDarkMode={isDarkMode}
              />
            </Collapse.Panel>
          </Collapse>
        </Layout.Content>
      </Layout>
      
      {/* Deny Log Modal */}
      <DenyLogModal
        visible={denyLogModalVisible}
        onClose={() => setDenyLogModalVisible(false)}
      />
      
      {/* YAML Editor Modal */}
      <YamlEditorModal
        visible={yamlEditorModalVisible}
        onClose={() => setYamlEditorModalVisible(false)}
        onSuccess={() => {
          // Reload data after successful YAML update
          handleManualReload();
        }}
      />
    </ConfigProvider>
  );
}
