import { useState, useEffect, useRef } from 'preact/hooks';
import { Modal, Button, Typography, Alert, Spin, Input } from 'antd';
import { FileTextOutlined, ReloadOutlined, ClearOutlined } from '@ant-design/icons';

const { TextArea } = Input;
const { Title, Text } = Typography;

export function DenyLogModal({ visible, onClose }) {
  const [loading, setLoading] = useState(false);
  const [logContents, setLogContents] = useState('');
  const [error, setError] = useState(null);
  const isMountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Get authentication token
  const getAuth = async () => {
    try {
      const auth = localStorage.getItem('hassTokens');
      if (auth) {
        const tokens = JSON.parse(auth);
        return tokens.access_token;
      }
      const sessionAuth = sessionStorage.getItem('hassTokens');
      if (sessionAuth) {
        const tokens = JSON.parse(sessionAuth);
        return tokens.access_token;
      }
      return null;
    } catch (error) {
      console.error('Auth error:', error);
      return null;
    }
  };

  // Fetch deny log contents
  const fetchDenyLog = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const token = await getAuth();
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch('/api/rbac/deny-log', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to fetch deny log');
      }

      const data = await response.json();
      if (data.success) {
        if (isMountedRef.current) {
          setLogContents(data.contents);
        }
      } else {
        throw new Error(data.error || 'Failed to fetch deny log');
      }
    } catch (error) {
      console.error('Error fetching deny log:', error);
      if (isMountedRef.current) {
        setError(error.message);
        setLogContents('');
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  };

  // Load log contents when modal opens
  useEffect(() => {
    if (visible) {
      isMountedRef.current = true; // Ensure we're marked as mounted when modal opens
      fetchDenyLog();
    }
  }, [visible]);

  // Clear log contents
  const handleClearLog = () => {
    Modal.confirm({
      title: 'Clear Deny Log',
      content: 'Are you sure you want to clear the deny log? This action cannot be undone.',
      okText: 'Clear',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          if (!isMountedRef.current) return;
          
          setLoading(true);
          setError(null);
          
          const token = await getAuth();
          if (!token) {
            throw new Error('Not authenticated');
          }

          const response = await fetch('/api/rbac/deny-log', {
            method: 'DELETE',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Failed to clear deny log');
          }

          const data = await response.json();
          if (data.success) {
            if (isMountedRef.current) {
              setLogContents('');
              // Don't show success modal to avoid conflicts - the cleared log content is feedback enough
            }
          } else {
            throw new Error(data.error || 'Failed to clear deny log');
          }
        } catch (error) {
          console.error('Error clearing deny log:', error);
          if (isMountedRef.current) {
            setError(error.message);
            // Only show error modal for actual errors
            Modal.error({
              title: 'Clear Failed',
              content: `Failed to clear deny log: ${error.message}`,
              getContainer: false, // Prevent portal conflicts
            });
          }
        } finally {
          if (isMountedRef.current) {
            setLoading(false);
          }
        }
      }
    });
  };

  // Format log contents for better readability
  const formatLogContents = (contents) => {
    if (!contents || contents.trim() === '') {
      return 'No deny log entries found.';
    }
    
    // Split by lines and reverse to show newest first
    const lines = contents.trim().split('\n').reverse();
    return lines.join('\n');
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileTextOutlined />
          <span>Access Denial Log</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      width={800}
      footer={[
        <Button key="clear" danger icon={<ClearOutlined />} onClick={handleClearLog}>
          Clear Log
        </Button>,
        <Button key="refresh" icon={<ReloadOutlined />} onClick={fetchDenyLog} loading={loading}>
          Refresh
        </Button>,
        <Button key="close" type="primary" onClick={onClose}>
          Close
        </Button>
      ]}
      style={{ top: 20 }}
    >
      <div style={{ marginBottom: '16px' }}>
        <Alert
          message="Deny Log Information"
          description="This log shows all access denials when deny list logging is enabled. Entries are shown with newest first."
          type="info"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      </div>

      {error && (
        <Alert
          message="Error Loading Log"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: '16px' }}
        />
      )}

      <div style={{ position: 'relative' }}>
        {loading && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 10
          }}>
            <Spin size="large" />
          </div>
        )}
        
        <TextArea
          value={formatLogContents(logContents)}
          readOnly
          rows={20}
          style={{
            fontFamily: 'Monaco, Consolas, "Courier New", monospace',
            fontSize: '12px',
            lineHeight: '1.4',
            backgroundColor: '#f5f5f5',
            opacity: loading ? 0.5 : 1
          }}
          placeholder="No deny log entries found. Access denials will appear here when deny list logging is enabled."
        />
      </div>

      <div style={{ marginTop: '12px', fontSize: '12px', color: '#666' }}>
        <Text type="secondary">
          Log file location: custom_components/rbac/deny_list.log
        </Text>
      </div>
    </Modal>
  );
}
