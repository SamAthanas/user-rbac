import { useState, useEffect } from 'preact/hooks';
import { Modal, Form, Input, Button, Space, Row, Col, Select, InputNumber, Switch, Divider, Typography, notification, Dropdown, Tooltip } from 'antd';
import { PlusOutlined, DeleteOutlined, CheckOutlined, CloseOutlined, ExclamationOutlined, ToolOutlined, CodeOutlined, DownOutlined } from '@ant-design/icons';
import CodeMirror from '@uiw/react-codemirror';
import { javascript } from '@codemirror/lang-javascript';

const { TextArea } = Input;
const { Text } = Typography;

export function RoleEditModal({ 
  visible, 
  onCancel, 
  onSave, 
  roleName, 
  roleConfig, 
  availableRoles = [],
  domains = [],
  entities = [],
  services = {}
}) {
  const [form] = Form.useForm();
  const [showTemplate, setShowTemplate] = useState(false);
  const [domainRestrictions, setDomainRestrictions] = useState([]);
  const [entityRestrictions, setEntityRestrictions] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [templateTestResult, setTemplateTestResult] = useState(null); // null, 'loading', 'true', 'false', 'error'
  const [templateTestError, setTemplateTestError] = useState('');
  const [templateValue, setTemplateValue] = useState('');
  const [templateEvaluatedValue, setTemplateEvaluatedValue] = useState(null);
  const [currentUserEntity, setCurrentUserEntity] = useState(null);
  const [showDomainSelects, setShowDomainSelects] = useState({});
  const [showEntitySelects, setShowEntitySelects] = useState({});

  useEffect(() => {
    if (visible && roleConfig) {
      // Initialize form with role data
      form.setFieldsValue({
        description: roleConfig.description || '',
        admin: roleConfig.admin || false,
        fallbackRole: roleConfig.fallbackRole || '',
        domains: roleConfig.permissions?.domains || {},
        entities: roleConfig.permissions?.entities || {}
      });
      
      // Initialize restrictions arrays
      const domainRestrictions = [];
      const entityRestrictions = [];
      
      if (roleConfig.permissions?.domains) {
        Object.entries(roleConfig.permissions.domains).forEach(([domain, config]) => {
          domainRestrictions.push({
            domain,
            services: config.services || [],
            allow: config.allow || false
          });
        });
      }
      
      if (roleConfig.permissions?.entities) {
        Object.entries(roleConfig.permissions.entities).forEach(([entity, config]) => {
          entityRestrictions.push({
            entity,
            services: config.services || [],
            allow: config.allow || false
          });
        });
      }
      
      setDomainRestrictions(domainRestrictions);
      setEntityRestrictions(entityRestrictions);
      setShowTemplate(!!roleConfig.template);
      setIsAdmin(roleConfig.admin || false);
      setTemplateTestResult(null);
      setTemplateTestError('');
      setTemplateValue(roleConfig.template || '');
      setTemplateEvaluatedValue(null);
      
      // Initialize show states for selects based on existing services
      const domainShowStates = {};
      const entityShowStates = {};
      
      domainRestrictions.forEach((restriction, index) => {
        domainShowStates[index] = restriction.services.length > 0;
      });
      
      entityRestrictions.forEach((restriction, index) => {
        entityShowStates[index] = restriction.services.length > 0;
      });
      
      setShowDomainSelects(domainShowStates);
      setShowEntitySelects(entityShowStates);
    } else if (visible) {
      // New role
      form.resetFields();
      setDomainRestrictions([]);
      setEntityRestrictions([]);
      setShowTemplate(false);
      setIsAdmin(false);
      setTemplateTestResult(null);
      setTemplateTestError('');
      setTemplateValue('');
      setTemplateEvaluatedValue(null);
      setShowDomainSelects({});
      setShowEntitySelects({});
    }
  }, [visible, roleConfig, form]);

  // Load current user entity when modal opens
  useEffect(() => {
    if (visible) {
      getCurrentUserEntity().then(entity => {
        setCurrentUserEntity(entity);
      });
    }
  }, [visible]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      
      // Convert restrictions arrays back to objects
      const domains = {};
      const entities = {};
      
      domainRestrictions.forEach(restriction => {
        domains[restriction.domain] = {
          services: restriction.services,
          allow: restriction.allow || false
        };
      });
      
      entityRestrictions.forEach(restriction => {
        entities[restriction.entity] = {
          services: restriction.services,
          allow: restriction.allow || false
        };
      });
      
      const roleData = {
        description: values.description,
        admin: values.admin || false,
        permissions: {
          domains,
          entities
        }
      };
      
      // Add template if provided
      if (showTemplate && templateValue) {
        roleData.template = templateValue;
        if (values.fallbackRole) {
          roleData.fallbackRole = values.fallbackRole;
        }
      }
      
      // For new roles, include the role name
      const saveData = {
        roleData,
        roleName: roleName || values.roleName  // Use existing name or new name from form
      };
      
      onSave(saveData);
    } catch (error) {
      console.error('Form validation failed:', error);
    }
  };

  const addDomainRestriction = () => {
    const newIndex = domainRestrictions.length;
    setDomainRestrictions([...domainRestrictions, { domain: '', services: [], allow: false }]);
    setShowDomainSelects({ ...showDomainSelects, [newIndex]: false });
  };

  const removeDomainRestriction = (index) => {
    setDomainRestrictions(domainRestrictions.filter((_, i) => i !== index));
    // Clean up show state for removed restriction
    const newShowStates = { ...showDomainSelects };
    delete newShowStates[index];
    // Reindex remaining states
    const reindexedStates = {};
    Object.keys(newShowStates).forEach(key => {
      const keyIndex = parseInt(key);
      if (keyIndex > index) {
        reindexedStates[keyIndex - 1] = newShowStates[key];
      } else if (keyIndex < index) {
        reindexedStates[keyIndex] = newShowStates[key];
      }
    });
    setShowDomainSelects(reindexedStates);
  };

  const updateDomainRestriction = (index, field, value) => {
    const updated = [...domainRestrictions];
    updated[index] = { ...updated[index], [field]: value };
    setDomainRestrictions(updated);
  };

  const addEntityRestriction = () => {
    const newIndex = entityRestrictions.length;
    setEntityRestrictions([...entityRestrictions, { entity: '', services: [], allow: false }]);
    setShowEntitySelects({ ...showEntitySelects, [newIndex]: false });
  };

  const removeEntityRestriction = (index) => {
    setEntityRestrictions(entityRestrictions.filter((_, i) => i !== index));
    // Clean up show state for removed restriction
    const newShowStates = { ...showEntitySelects };
    delete newShowStates[index];
    // Reindex remaining states
    const reindexedStates = {};
    Object.keys(newShowStates).forEach(key => {
      const keyIndex = parseInt(key);
      if (keyIndex > index) {
        reindexedStates[keyIndex - 1] = newShowStates[key];
      } else if (keyIndex < index) {
        reindexedStates[keyIndex] = newShowStates[key];
      }
    });
    setShowEntitySelects(reindexedStates);
  };

  const updateEntityRestriction = (index, field, value) => {
    const updated = [...entityRestrictions];
    updated[index] = { ...updated[index], [field]: value };
    setEntityRestrictions(updated);
  };

  const showDomainSelect = (index) => {
    setShowDomainSelects({ ...showDomainSelects, [index]: true });
  };

  const showEntitySelect = (index) => {
    setShowEntitySelects({ ...showEntitySelects, [index]: true });
  };

  const getServicesForDomain = (domain) => {
    return services.domains?.[domain] || [];
  };

  const getServicesForEntity = (entity) => {
    return services.entities?.[entity] || [];
  };

  const getHAAuth = async () => {
    try {
      const homeAssistantElement = document.querySelector("home-assistant");
      if (homeAssistantElement && homeAssistantElement.hass) {
        const hass = homeAssistantElement.hass;
        if (hass.auth?.data?.access_token) {
          return { access_token: hass.auth.data.access_token };
        }
        if (hass.auth?.access_token) {
          return { access_token: hass.auth.access_token };
        }
      }
      
      const auth = localStorage.getItem('hassTokens') || sessionStorage.getItem('hassTokens');
      if (auth) {
        const tokens = JSON.parse(auth);
        return { access_token: tokens.access_token };
      }
      
      return null;
    } catch (error) {
      console.error('Auth error:', error);
      return null;
    }
  };

  const handleOpenHAEditor = () => {
    // Get the current domain and redirect to HA template editor
    const currentUrl = window.location.href;
    const url = new URL(currentUrl);
    const domain = url.hostname;
    const protocol = url.protocol;
    const port = url.port ? `:${url.port}` : '';
    const editorUrl = `${protocol}//${domain}${port}/developer-tools/template`;
    window.open(editorUrl, '_blank');
  };

  const handleClearTemplate = () => {
    setTemplateValue('');
    setTemplateTestResult(null);
    setTemplateEvaluatedValue(null);
    setTemplateTestError('');
    form.setFieldsValue({ fallbackRole: '' });
    setShowTemplate(false); // This will hide the template section and show "Add Template" button
  };

  const getCurrentUserEntity = async () => {
    try {
      const auth = await getHAAuth();
      if (!auth) return null;
      
      const response = await fetch('/api/rbac/current-user', {
        headers: { 'Authorization': `Bearer ${auth.access_token}` }
      });
      
      if (response.ok) {
        const userData = await response.json();
        return userData.person_entity_id;
      }
      return null;
    } catch (error) {
      console.error('Error getting current user entity:', error);
      return null;
    }
  };

  const handleInsertUserVariable = (type = 'variable') => {
    if (currentUserEntity) {
      let templateToInsert = '';
      
      switch (type) {
        case 'variable':
          templateToInsert = `current_user_str`;
          break;
        case 'home':
          templateToInsert = `states[current_user_str].state == 'home'`;
          break;
        case 'away':
          templateToInsert = `states[current_user_str].state != 'home'`;
          break;
        default:
          templateToInsert = `{{ states(current_user_str) }}`;
      }
      
      const newValue = templateValue + templateToInsert;
      setTemplateValue(newValue);
      setTemplateTestResult(null);
      setTemplateEvaluatedValue(null);
    }
  };

  const handleTestTemplate = async () => {
    try {
      setTemplateTestResult('loading');
      setTemplateTestError('');
      
      if (!templateValue) {
        setTemplateTestResult('error');
        setTemplateTestError('No template to test');
        notification.error({
          message: 'Template Test Failed',
          description: 'Please enter a template first',
          placement: 'topRight',
          duration: 3,
        });
        return;
      }
      
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }
      
      const response = await fetch('/api/rbac/evaluate-template', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          template: templateValue
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setTemplateTestResult(data.result ? 'true' : 'false');
        setTemplateEvaluatedValue(data.evaluated_value);
      } else {
        setTemplateTestResult('error');
        setTemplateTestError(data.error);
        setTemplateEvaluatedValue(null);
        notification.error({
          message: 'Template Evaluation Error',
          description: data.error,
          placement: 'topRight',
          duration: 5,
        });
      }
    } catch (error) {
      console.error('Error testing template:', error);
      setTemplateTestResult('error');
      setTemplateTestError(error.message);
      setTemplateEvaluatedValue(null);
      notification.error({
        message: 'Template Test Failed',
        description: error.message,
        placement: 'topRight',
        duration: 5,
      });
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: '40px' }}>
          <span>{roleName ? `Edit Role: ${roleName}` : 'Create New Role'}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Text style={{ fontSize: '14px' }}>Admin Role</Text>
            <Switch
              checked={isAdmin}
              onChange={(checked) => {
                setIsAdmin(checked);
                form.setFieldsValue({ admin: checked });
              }}
            />
          </div>
        </div>
      }
      open={visible}
      onCancel={onCancel}
      onOk={handleSave}
      width={800}
      okText="Save Role"
      cancelText="Cancel"
    >
      <Form form={form} layout="vertical">
        {!roleName && (
          <Form.Item
            name="roleName"
            label="Role Name"
            rules={[
              { required: true, message: 'Please enter a role name' },
              { pattern: /^[a-z0-9_]+$/, message: 'Role name must be lowercase letters, numbers, and underscores only' }
            ]}
            help="Use lowercase letters, numbers, and underscores (e.g., 'power_user', 'guest', 'moderator')"
          >
            <Input placeholder="Enter role name (e.g., 'power_user')" />
          </Form.Item>
        )}

        <Form.Item
          name="description"
          label="Description"
          rules={[{ required: true, message: 'Please enter a description' }]}
        >
          <Input placeholder="Enter role description" />
        </Form.Item>

        <Form.Item name="admin" hidden>
          <Input />
        </Form.Item>

        {!isAdmin && (
          <>
            <Divider>Template Configuration</Divider>
        
        {!showTemplate ? (
          <Button 
            type="dashed" 
            icon={<PlusOutlined />} 
            onClick={() => setShowTemplate(true)}
            style={{ width: '100%', marginBottom: 16 }}
          >
            Add Template
          </Button>
        ) : (
          <div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Button
                    size="small"
                    type="text"
                    icon={<CloseOutlined />}
                    onClick={handleClearTemplate}
                    style={{
                      color: '#ff4d4f',
                      border: 'none',
                      padding: '4px',
                      minWidth: 'auto',
                      width: '24px',
                      height: '24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#ff4d4f';
                      e.currentTarget.style.color = 'white';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = '#ff4d4f';
                    }}
                    title="Clear template settings"
                  />
                  <Text strong>Template</Text>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Button
                    size="small"
                    icon={<ToolOutlined />}
                    onClick={handleOpenHAEditor}
                    title="Open Home Assistant Template Editor"
                  >
                    HA Editor
                  </Button>
                  <Button
                    size="small"
                    loading={templateTestResult === 'loading'}
                    onClick={handleTestTemplate}
                    type={templateTestResult === 'true' ? 'primary' : templateTestResult === 'false' || templateTestResult === 'error' ? 'default' : 'default'}
                    style={{
                      backgroundColor: templateTestResult === 'true' ? '#52c41a' : templateTestResult === 'false' ? '#ff4d4f' : templateTestResult === 'error' ? '#faad14' : undefined,
                      color: templateTestResult ? 'white' : undefined,
                      borderColor: templateTestResult === 'true' ? '#52c41a' : templateTestResult === 'false' ? '#ff4d4f' : templateTestResult === 'error' ? '#faad14' : undefined,
                      minWidth: '100px',
                    }}
                    icon={
                      templateTestResult === 'true' ? <CheckOutlined /> :
                      templateTestResult === 'false' ? <CloseOutlined /> :
                      templateTestResult === 'error' ? <ExclamationOutlined /> :
                      <CodeOutlined />
                    }
                  >
                    {templateTestResult === 'true' ? 'True' : 
                     templateTestResult === 'false' ? 'False' : 
                     templateTestResult === 'error' ? 'Error' : 
                     'Test'}
                  </Button>
                </div>
              </div>
              <div style={{ position: 'relative' }}>
                <CodeMirror
                  value={templateValue}
                  height="150px"
                  extensions={[javascript({ jsx: true })]}
                  onChange={(value) => {
                    setTemplateValue(value);
                    setTemplateTestResult(null);
                    setTemplateEvaluatedValue(null);
                  }}
                  placeholder="Enter Jinja2 template (e.g., {{ states(current_user_str) == 'home' }})"
                  theme="light"
                  basicSetup={{
                    lineNumbers: true,
                    highlightActiveLineGutter: true,
                    highlightSpecialChars: true,
                    foldGutter: true,
                    drawSelection: true,
                    dropCursor: true,
                    allowMultipleSelections: true,
                    indentOnInput: true,
                    bracketMatching: true,
                    closeBrackets: true,
                    autocompletion: true,
                    rectangularSelection: true,
                    crosshairCursor: true,
                    highlightActiveLine: true,
                    highlightSelectionMatches: true,
                    closeBracketsKeymap: true,
                    searchKeymap: true,
                    foldKeymap: true,
                    completionKeymap: true,
                    lintKeymap: true,
                  }}
                  style={{
                    border: '1px solid #d9d9d9',
                    borderRadius: '6px',
                    overflow: 'hidden',
                  }}
                />
                {currentUserEntity && (
                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: 'variable',
                          label: 'Insert user variable',
                          icon: <CodeOutlined />,
                          onClick: () => handleInsertUserVariable('variable')
                        },
                        {
                          key: 'home',
                          label: 'Check if home',
                          icon: <CheckOutlined />,
                          onClick: () => handleInsertUserVariable('home')
                        },
                        {
                          key: 'away',
                          label: 'Check if away',
                          icon: <CloseOutlined />,
                          onClick: () => handleInsertUserVariable('away')
                        }
                      ]
                    }}
                    trigger={['click']}
                    placement="topRight"
                  >
                    <Button
                      type="primary"
                      size="small"
                      icon={<CodeOutlined />}
                      style={{
                        position: 'absolute',
                        bottom: '8px',
                        right: '8px',
                        zIndex: 10,
                        fontSize: '12px',
                        height: '28px',
                        padding: '0 8px',
                      }}
                      title="Insert user template snippets"
                    >
                      Insert User <DownOutlined />
                    </Button>
                  </Dropdown>
                )}
              </div>
              <Text type="secondary" style={{ fontSize: '12px' }}>
                {templateTestResult && templateEvaluatedValue !== null ? (
                  <>
                    <strong>Evaluated result:</strong> {String(templateEvaluatedValue)}
                  </>
                ) : (
                  'Jinja2 template that determines when this role should be active. If false, the fallback role will be used.'
                )}
              </Text>
            </div>
            
            <Form.Item
              name="fallbackRole"
              label="Fallback Role"
              help="Role to use when template evaluates to false"
            >
              <Select 
                showSearch
                placeholder="Select fallback role"
                filterOption={(input, option) =>
                  option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                }
              >
                {availableRoles.filter(role => role !== roleName).map(role => (
                  <Select.Option key={role} value={role}>{role}</Select.Option>
                ))}
              </Select>
            </Form.Item>
            
            <Text type="secondary" style={{ fontSize: '12px', fontStyle: 'italic' }}>
              When the template evaluates to false, users with this role will automatically be assigned the fallback role instead.
            </Text>
          </div>
        )}


        <Divider>Domain Restrictions</Divider>
        
        {domainRestrictions.map((restriction, index) => (
          <div key={index} style={{ marginBottom: 16, padding: 16, border: '1px solid #f0f0f0', borderRadius: 6 }} data-restriction-index={index}>
            <Row gutter={16} align="middle">
              <Col span={10}>
                <Select
                  showSearch
                  placeholder="Select domain"
                  value={restriction.domain}
                  onChange={(value) => updateDomainRestriction(index, 'domain', value)}
                  style={{ width: '100%' }}
                  filterOption={(input, option) =>
                    option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                  }
                >
                  {domains.map(domain => (
                    <Select.Option key={domain} value={domain}>{domain}</Select.Option>
                  ))}
                </Select>
              </Col>
              <Col span={10}>
                {!showDomainSelects[index] ? (
                  <Tooltip title={restriction.allow ? "Add specific services to allow" : "Add specific service restrictions"}>
                    <Button
                      type="dashed"
                      icon={<PlusOutlined />}
                      onClick={() => showDomainSelect(index)}
                      style={{
                        width: '100%',
                        height: '32px',
                        border: '2px dashed #d9d9d9',
                        background: 'transparent',
                        color: '#999',
                        opacity: 0.6,
                        transition: 'all 0.3s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.opacity = '1';
                        e.currentTarget.style.borderColor = '#1890ff';
                        e.currentTarget.style.color = '#1890ff';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = '0.6';
                        e.currentTarget.style.borderColor = '#d9d9d9';
                        e.currentTarget.style.color = '#999';
                      }}
                    >
                      {restriction.allow ? "Allow Services" : "Restrict Services"}
                    </Button>
                  </Tooltip>
                ) : (
                  <Select
                    mode="multiple"
                    showSearch
                    placeholder={restriction.allow ? "Select services to allow (empty = allow all)" : "Select services to block (empty = block all)"}
                    value={restriction.services}
                    onChange={(value) => updateDomainRestriction(index, 'services', value)}
                    style={{ width: '100%' }}
                    filterOption={(input, option) =>
                      option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                    }
                  >
                    {getServicesForDomain(restriction.domain).map(service => (
                      <Select.Option key={service} value={service}>{service}</Select.Option>
                    ))}
                  </Select>
                )}
              </Col>
              <Col span={2}>
                <Tooltip title={restriction.allow ? "Allow this domain/services" : "Block this domain/services"}>
                  <Switch
                    size="small"
                    checked={restriction.allow}
                    onChange={(checked) => updateDomainRestriction(index, 'allow', checked)}
                    checkedChildren="✓"
                    unCheckedChildren="✗"
                  />
                </Tooltip>
              </Col>
              <Col span={2}>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeDomainRestriction(index)}
                />
              </Col>
            </Row>
          </div>
        ))}
        
        <Button 
          type="dashed" 
          icon={<PlusOutlined />} 
          onClick={addDomainRestriction}
          style={{ width: '100%', marginBottom: 16 }}
        >
          Add Domain Restriction
        </Button>

        <Divider>Entity Restrictions</Divider>
        
        {entityRestrictions.map((restriction, index) => (
          <div key={index} style={{ marginBottom: 16, padding: 16, border: '1px solid #f0f0f0', borderRadius: 6 }} data-restriction-index={index}>
            <Row gutter={16} align="middle">
              <Col span={10}>
                <Select
                  showSearch
                  placeholder="Select entity"
                  value={restriction.entity}
                  onChange={(value) => updateEntityRestriction(index, 'entity', value)}
                  style={{ width: '100%' }}
                  filterOption={(input, option) =>
                    option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                  }
                >
                  {entities.map(entity => (
                    <Select.Option key={entity} value={entity}>{entity}</Select.Option>
                  ))}
                </Select>
              </Col>
              <Col span={10}>
                {!showEntitySelects[index] ? (
                  <Tooltip title={restriction.allow ? "Add specific services to allow" : "Add specific service restrictions"}>
                    <Button
                      type="dashed"
                      icon={<PlusOutlined />}
                      onClick={() => showEntitySelect(index)}
                      style={{
                        width: '100%',
                        height: '32px',
                        border: '2px dashed #d9d9d9',
                        background: 'transparent',
                        color: '#999',
                        opacity: 0.6,
                        transition: 'all 0.3s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.opacity = '1';
                        e.currentTarget.style.borderColor = '#1890ff';
                        e.currentTarget.style.color = '#1890ff';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = '0.6';
                        e.currentTarget.style.borderColor = '#d9d9d9';
                        e.currentTarget.style.color = '#999';
                      }}
                    >
                      {restriction.allow ? "Allow Services" : "Restrict Services"}
                    </Button>
                  </Tooltip>
                ) : (
                  <Select
                    mode="multiple"
                    showSearch
                    placeholder={restriction.allow ? "Select services to allow (empty = allow all)" : "Select services to block (empty = block all)"}
                    value={restriction.services}
                    onChange={(value) => updateEntityRestriction(index, 'services', value)}
                    style={{ width: '100%' }}
                    filterOption={(input, option) =>
                      option.children.toLowerCase().indexOf(input.toLowerCase()) >= 0
                    }
                  >
                    {getServicesForEntity(restriction.entity).map(service => (
                      <Select.Option key={service} value={service}>{service}</Select.Option>
                    ))}
                  </Select>
                )}
              </Col>
              <Col span={2}>
                <Tooltip title={restriction.allow ? "Allow this entity/services" : "Block this entity/services"}>
                  <Switch
                    size="small"
                    checked={restriction.allow}
                    onChange={(checked) => updateEntityRestriction(index, 'allow', checked)}
                    checkedChildren="✓"
                    unCheckedChildren="✗"
                  />
                </Tooltip>
              </Col>
              <Col span={2}>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeEntityRestriction(index)}
                />
              </Col>
            </Row>
          </div>
        ))}
        
        <Button 
          type="dashed" 
          icon={<PlusOutlined />} 
          onClick={addEntityRestriction}
          style={{ width: '100%' }}
        >
          Add Entity Restriction
        </Button>
          </>
        )}
      </Form>
    </Modal>
  );
}