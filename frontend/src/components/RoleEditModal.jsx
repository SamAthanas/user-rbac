import { useState, useEffect } from 'preact/hooks';
import { Modal, Form, Input, Button, Space, Row, Col, Select, InputNumber, Switch, Divider, Typography } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';

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

  useEffect(() => {
    if (visible && roleConfig) {
      // Initialize form with role data
      form.setFieldsValue({
        description: roleConfig.description || '',
        template: roleConfig.template || '',
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
            hide: config.hide || false,
            services: config.services || []
          });
        });
      }
      
      if (roleConfig.permissions?.entities) {
        Object.entries(roleConfig.permissions.entities).forEach(([entity, config]) => {
          entityRestrictions.push({
            entity,
            hide: config.hide || false,
            services: config.services || []
          });
        });
      }
      
      setDomainRestrictions(domainRestrictions);
      setEntityRestrictions(entityRestrictions);
      setShowTemplate(!!roleConfig.template);
    } else if (visible) {
      // New role
      form.resetFields();
      setDomainRestrictions([]);
      setEntityRestrictions([]);
      setShowTemplate(false);
    }
  }, [visible, roleConfig, form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      
      // Convert restrictions arrays back to objects
      const domains = {};
      const entities = {};
      
      domainRestrictions.forEach(restriction => {
        domains[restriction.domain] = {
          hide: restriction.hide,
          services: restriction.services
        };
      });
      
      entityRestrictions.forEach(restriction => {
        entities[restriction.entity] = {
          hide: restriction.hide,
          services: restriction.services
        };
      });
      
      const roleData = {
        description: values.description,
        permissions: {
          domains,
          entities
        }
      };
      
      // Add template if provided
      if (showTemplate && values.template) {
        roleData.template = values.template;
        if (values.fallbackRole) {
          roleData.fallbackRole = values.fallbackRole;
        }
      }
      
      onSave(roleData);
    } catch (error) {
      console.error('Form validation failed:', error);
    }
  };

  const addDomainRestriction = () => {
    setDomainRestrictions([...domainRestrictions, { domain: '', hide: false, services: [] }]);
  };

  const removeDomainRestriction = (index) => {
    setDomainRestrictions(domainRestrictions.filter((_, i) => i !== index));
  };

  const updateDomainRestriction = (index, field, value) => {
    const updated = [...domainRestrictions];
    updated[index] = { ...updated[index], [field]: value };
    setDomainRestrictions(updated);
  };

  const addEntityRestriction = () => {
    setEntityRestrictions([...entityRestrictions, { entity: '', hide: false, services: [] }]);
  };

  const removeEntityRestriction = (index) => {
    setEntityRestrictions(entityRestrictions.filter((_, i) => i !== index));
  };

  const updateEntityRestriction = (index, field, value) => {
    const updated = [...entityRestrictions];
    updated[index] = { ...updated[index], [field]: value };
    setEntityRestrictions(updated);
  };

  const getServicesForDomain = (domain) => {
    return services.domains?.[domain] || [];
  };

  const getServicesForEntity = (entity) => {
    return services.entities?.[entity] || [];
  };

  return (
    <Modal
      title={roleName ? `Edit Role: ${roleName}` : 'Create New Role'}
      open={visible}
      onCancel={onCancel}
      onOk={handleSave}
      width={800}
      okText="Save Role"
      cancelText="Cancel"
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="description"
          label="Description"
          rules={[{ required: true, message: 'Please enter a description' }]}
        >
          <Input placeholder="Enter role description" />
        </Form.Item>

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
            <Form.Item
              name="template"
              label="Template"
              help="Jinja2 template that determines when this role should be active. If false, the fallback role will be used."
            >
              <TextArea 
                rows={4} 
                placeholder="Enter Jinja2 template (e.g., {{ states('person.john') == 'home' }})"
              />
            </Form.Item>
            
            <Form.Item
              name="fallbackRole"
              label="Fallback Role"
              help="Role to use when template evaluates to false"
            >
              <Select placeholder="Select fallback role">
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
          <div key={index} style={{ marginBottom: 16, padding: 16, border: '1px solid #f0f0f0', borderRadius: 6 }}>
            <Row gutter={16} align="middle">
              <Col span={8}>
                <Select
                  placeholder="Select domain"
                  value={restriction.domain}
                  onChange={(value) => updateDomainRestriction(index, 'domain', value)}
                  style={{ width: '100%' }}
                >
                  {domains.map(domain => (
                    <Select.Option key={domain} value={domain}>{domain}</Select.Option>
                  ))}
                </Select>
              </Col>
              <Col span={6}>
                <Switch
                  checked={restriction.hide}
                  onChange={(checked) => updateDomainRestriction(index, 'hide', checked)}
                  checkedChildren="Hide"
                  unCheckedChildren="Show"
                />
              </Col>
              <Col span={8}>
                <Select
                  mode="multiple"
                  placeholder="Select services to block"
                  value={restriction.services}
                  onChange={(value) => updateDomainRestriction(index, 'services', value)}
                  style={{ width: '100%' }}
                >
                  {getServicesForDomain(restriction.domain).map(service => (
                    <Select.Option key={service} value={service}>{service}</Select.Option>
                  ))}
                </Select>
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
          <div key={index} style={{ marginBottom: 16, padding: 16, border: '1px solid #f0f0f0', borderRadius: 6 }}>
            <Row gutter={16} align="middle">
              <Col span={8}>
                <Select
                  placeholder="Select entity"
                  value={restriction.entity}
                  onChange={(value) => updateEntityRestriction(index, 'entity', value)}
                  style={{ width: '100%' }}
                >
                  {entities.map(entity => (
                    <Select.Option key={entity} value={entity}>{entity}</Select.Option>
                  ))}
                </Select>
              </Col>
              <Col span={6}>
                <Switch
                  checked={restriction.hide}
                  onChange={(checked) => updateEntityRestriction(index, 'hide', checked)}
                  checkedChildren="Hide"
                  unCheckedChildren="Show"
                />
              </Col>
              <Col span={8}>
                <Select
                  mode="multiple"
                  placeholder="Select services to block"
                  value={restriction.services}
                  onChange={(value) => updateEntityRestriction(index, 'services', value)}
                  style={{ width: '100%' }}
                >
                  {getServicesForEntity(restriction.entity).map(service => (
                    <Select.Option key={service} value={service}>{service}</Select.Option>
                  ))}
                </Select>
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
      </Form>
    </Modal>
  );
}