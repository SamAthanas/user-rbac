import { Avatar, Typography, Dropdown, Button } from 'antd';
import { HomeOutlined, LogoutOutlined, SettingOutlined } from '@ant-design/icons';

export function Header({ currentUser = null }) {
  // Check if we're running inside an iframe (sidebar panel)
  const isInIframe = () => {
    try {
      return window.self !== window.top;
    } catch (e) {
      return true;
    }
  };

  const getUserPicture = (user) => {
    console.log('Header getUserPicture called with user:', user);
    
    // Use the entity_picture from the person entity if available
    if (user?.entity_picture) {
      console.log('Using entity_picture:', user.entity_picture);
      return user.entity_picture;
    }
    
    // Fallback: construct URL from user ID (for backwards compatibility)
    if (user?.id) {
      const fallbackUrl = `/api/image/serve/${user.id}/512x512`;
      console.log('Using fallback URL:', fallbackUrl);
      return fallbackUrl;
    }
    
    console.log('No picture available for user');
    return null;
  };

  const getUserDisplayName = (user) => {
    return user?.name || 'Unknown User';
  };

  const handleReturnToHA = () => {
    // Get the current domain and redirect to base domain
    const currentUrl = window.location.href;
    const url = new URL(currentUrl);
    window.location.href = `${url.protocol}//${url.hostname}${url.port ? ':' + url.port : ''}/`;
  };

  const handleReturnToIntegration = () => {
    // Get the current domain and redirect to RBAC integration page
    const currentUrl = window.location.href;
    const url = new URL(currentUrl);
    const domain = url.hostname;
    const protocol = url.protocol;
    const port = url.port ? `:${url.port}` : '';
    const integrationUrl = `${protocol}//${domain}${port}/config/integrations/integration/rbac`;
    
    // If we're in an iframe (sidebar panel), open in new tab
    if (isInIframe()) {
      window.open(integrationUrl, '_blank');
    } else {
      window.location.href = integrationUrl;
    }
  };

  const handleLogout = () => {
    // Clear HA tokens from localStorage and sessionStorage
    localStorage.removeItem('hassTokens');
    sessionStorage.removeItem('hassTokens');
    
    // Redirect to Home Assistant login
    const currentUrl = window.location.href;
    const url = new URL(currentUrl);
    window.location.href = `${url.protocol}//${url.hostname}${url.port ? ':' + url.port : ''}/auth/authorize`;
  };

  const userMenuItems = [
    // Only show "Return to Home Assistant" if not in iframe (sidebar panel)
    ...(!isInIframe() ? [{
      key: 'home',
      label: 'Return to Home Assistant',
      icon: <HomeOutlined />,
      onClick: handleReturnToHA,
    }] : []),
    {
      key: 'integration',
      label: 'RBAC Integration',
      icon: <SettingOutlined />,
      onClick: handleReturnToIntegration,
    },
    {
      key: 'logout',
      label: 'Log Out',
      icon: <LogoutOutlined />,
      onClick: handleLogout,
    },
  ];

  return (
    <div style={{ 
      background: 'white',
      padding: '20px',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      display: 'flex', 
      justifyContent: 'space-between', 
      alignItems: 'center',
      marginBottom: '24px'
    }}>
      <div>
        <h1 style={{ margin: 0, color: '#1976d2' }}>🔐 RBAC Configuration</h1>
        <p style={{ margin: 0, color: '#666' }}>Manage role-based access control for your Home Assistant instance</p>
      </div>
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {currentUser && (
          <Dropdown
            menu={{ items: userMenuItems }}
            trigger={['click']}
            placement="bottomRight"
          >
            <div 
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '12px',
                padding: '8px 12px',
                borderRadius: '8px',
                cursor: 'pointer',
                transition: 'background-color 0.2s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = '#f5f5f5';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent';
              }}
            >
              <Avatar
                src={getUserPicture(currentUser)}
                size={48}
              >
                {getUserDisplayName(currentUser).charAt(0).toUpperCase()}
              </Avatar>
              <div>
                <Typography.Text strong style={{ fontSize: '16px' }}>
                  {getUserDisplayName(currentUser)}
                </Typography.Text>
                <br />
                <Typography.Text type="secondary" style={{ fontSize: '12px' }}>
                  {currentUser.role || 'No role assigned'}
                </Typography.Text>
              </div>
            </div>
          </Dropdown>
        )}
      </div>
    </div>
  );
}
