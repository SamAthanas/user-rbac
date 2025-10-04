import { useState, useEffect } from 'preact/hooks';
import { Modal, Button, Space, Typography, notification } from 'antd';
import { SaveOutlined, ReloadOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { getHAAuth, makeAuthenticatedRequest } from '../utils/auth';

const { Text } = Typography;

export function YamlEditorModal({ visible, onClose, onSuccess }) {
  const [yamlContent, setYamlContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Load YAML content when modal opens
  useEffect(() => {
    if (visible) {
      loadYamlContent();
    }
  }, [visible]);

  const loadYamlContent = async () => {
    setLoading(true);
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/yaml-editor', {
        method: 'GET'
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to load YAML content');
      }

      const data = await response.json();
      setYamlContent(data.yaml_content || '');
    } catch (error) {
      console.error('Error loading YAML content:', error);
      notification.error({
        message: 'Error Loading YAML',
        description: error.message,
        placement: 'bottomRight',
        duration: 5,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await makeAuthenticatedRequest('/api/rbac/yaml-editor', {
        method: 'POST',
        body: JSON.stringify({
          yaml_content: yamlContent,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to save YAML content');
      }

      notification.success({
        message: 'YAML Updated Successfully',
        description: data.message || 'Configuration has been saved',
        placement: 'bottomRight',
        duration: 3,
      });

      onSuccess?.();
      onClose();
    } catch (error) {
      console.error('Error saving YAML content:', error);
      notification.error({
        message: 'Error Saving YAML',
        description: error.message,
        placement: 'bottomRight',
        duration: 5,
      });
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    onClose();
  };

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#1890ff' }} />
          <span>Edit YAML Configuration</span>
        </Space>
      }
      open={visible}
      onCancel={handleCancel}
      width="90%"
      style={{ maxWidth: '1200px' }}
      footer={
        <Space>
          <Button 
            icon={<ReloadOutlined />} 
            onClick={loadYamlContent}
            loading={loading}
            disabled={saving}
          >
            Reload
          </Button>
          <Button onClick={handleCancel} disabled={saving}>
            Cancel
          </Button>
          <Button 
            type="primary" 
            icon={<SaveOutlined />} 
            onClick={handleSave}
            loading={saving}
            disabled={loading}
          >
            Save Changes
          </Button>
        </Space>
      }
    >
      <div style={{ marginBottom: 16 }}>
        <Text type="secondary">
          Edit the access_control.yaml configuration directly. Changes will be validated before saving.
        </Text>
      </div>
      
      <div style={{ border: '1px solid #d9d9d9', borderRadius: '6px', overflow: 'hidden' }}>
        <CodeMirror
          value={yamlContent}
          height="500px"
          onChange={(value) => {
            setYamlContent(value);
          }}
          editable={!loading}
          basicSetup={{
            lineNumbers: true,
            foldGutter: true,
            dropCursor: false,
            allowMultipleSelections: false,
            indentOnInput: true,
            bracketMatching: true,
            closeBrackets: true,
            autocompletion: true,
            highlightSelectionMatches: false,
            searchKeymap: true,
          }}
        />
      </div>
    </Modal>
  );
}
