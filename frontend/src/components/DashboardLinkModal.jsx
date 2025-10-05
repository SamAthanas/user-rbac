import { useState, useEffect } from 'preact/hooks';
import { Modal, Input, Button, Space, Typography, message, Divider } from 'antd';
import { CopyOutlined, LinkOutlined, CloseOutlined } from '@ant-design/icons';
import QRCode from 'qrcode';

const { Text } = Typography;

export function DashboardLinkModal({ 
  visible, 
  onClose, 
  guestUser,
  onSuccess, 
  onError 
}) {
  const [dashboardLink, setDashboardLink] = useState('');
  const [copying, setCopying] = useState(false);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState('');
  const [qrCodeLoading, setQrCodeLoading] = useState(false);

  // Generate dashboard link and QR code when modal opens
  useEffect(() => {
    if (visible && guestUser) {
      const baseUrl = window.location.origin;
      const link = `${baseUrl}/api/rbac/static/dashboard/${guestUser.id}`;
      setDashboardLink(link);
      
      // Generate QR code
      generateQRCode(link);
    }
  }, [visible, guestUser]);

  const generateQRCode = async (url) => {
    setQrCodeLoading(true);
    try {
      const qrCodeUrl = await QRCode.toDataURL(url, {
        width: 200,
        margin: 2,
        color: {
          dark: '#000000',
          light: '#FFFFFF'
        }
      });
      setQrCodeDataUrl(qrCodeUrl);
    } catch (error) {
      console.error('Error generating QR code:', error);
      message.error('Failed to generate QR code', 2);
    } finally {
      setQrCodeLoading(false);
    }
  };

  const handleCopyLink = async () => {
    if (!dashboardLink) return;
    
    setCopying(true);
    try {
      await navigator.clipboard.writeText(dashboardLink);
      message.success('Dashboard link copied to clipboard!', 2);
    } catch (error) {
      console.error('Failed to copy link:', error);
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = dashboardLink;
      document.body.appendChild(textArea);
      textArea.select();
      try {
        document.execCommand('copy');
        message.success('Dashboard link copied to clipboard!', 2);
      } catch (fallbackError) {
        console.error('Fallback copy failed:', fallbackError);
        message.error('Failed to copy link to clipboard', 2);
      }
      document.body.removeChild(textArea);
    } finally {
      setCopying(false);
    }
  };

  const handleClose = () => {
    setDashboardLink('');
    setQrCodeDataUrl('');
    setQrCodeLoading(false);
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <LinkOutlined style={{ color: '#1890ff' }} />
          <span>Guest Dashboard Link</span>
        </Space>
      }
      open={visible}
      onCancel={handleClose}
      footer={[
        <Button key="close" onClick={handleClose}>
          Close
        </Button>
      ]}
      width={600}
      centered
    >
      <div style={{ padding: '16px 0' }}>
        <div style={{ marginBottom: '16px' }}>
          <Text type="secondary" style={{ fontSize: '14px' }}>
            Share this link with <strong>{guestUser?.name}</strong> to give them access to their guest dashboard:
          </Text>
        </div>

        {/* Dashboard Link Input */}
        <div style={{ marginBottom: '24px' }}>
          <Input
            value={dashboardLink}
            readOnly
            placeholder="Dashboard link will appear here..."
            style={{
              fontFamily: 'monospace',
              fontSize: '12px',
              backgroundColor: '#f5f5f5'
            }}
            suffix={
              <Button
                type="text"
                icon={<CopyOutlined />}
                loading={copying}
                onClick={handleCopyLink}
                style={{
                  color: '#1890ff',
                  border: 'none',
                  padding: '4px 8px'
                }}
                title="Copy to clipboard"
              />
            }
          />
        </div>

        <Divider />

        {/* QR Code Section */}
        <div style={{ textAlign: 'center', marginTop: '24px' }}>
          <Text type="secondary" style={{ fontSize: '14px', display: 'block', marginBottom: '16px' }}>
            Scan QR code to open dashboard on mobile:
          </Text>
          
          {/* QR Code Display */}
          <div
            style={{
              width: '200px',
              height: '200px',
              border: '1px solid #d9d9d9',
              borderRadius: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto',
              backgroundColor: '#ffffff',
              overflow: 'hidden'
            }}
          >
            {qrCodeLoading ? (
              <div style={{ textAlign: 'center', color: '#999' }}>
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>⏳</div>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Generating QR Code...
                </Text>
              </div>
            ) : qrCodeDataUrl ? (
              <img 
                src={qrCodeDataUrl} 
                alt="Dashboard QR Code" 
                style={{ 
                  width: '100%', 
                  height: '100%',
                  objectFit: 'contain'
                }}
              />
            ) : (
              <div style={{ textAlign: 'center', color: '#999' }}>
                <div style={{ fontSize: '24px', marginBottom: '8px' }}>📱</div>
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  QR Code<br />
                  Not Available
                </Text>
              </div>
            )}
          </div>
        </div>

        <div style={{ 
          marginTop: '24px',
          padding: '12px', 
          backgroundColor: '#f6ffed', 
          border: '1px solid #b7eb8f', 
          borderRadius: '6px'
        }}>
          <Text type="secondary" style={{ fontSize: '12px' }}>
            <strong>Note:</strong> This link provides temporary access to the guest dashboard. 
            The guest user will be able to control the system based on their assigned role permissions.
          </Text>
        </div>
      </div>
    </Modal>
  );
}
