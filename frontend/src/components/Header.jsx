import { Avatar, Typography } from 'antd';

export function Header({ currentUser = null }) {
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
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
        )}
      </div>
    </div>
  );
}
