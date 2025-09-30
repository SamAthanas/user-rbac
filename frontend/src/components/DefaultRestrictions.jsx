import { useState, useEffect } from 'preact/hooks';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col
} from 'antd';
import { AntMultiSelect } from './AntMultiSelect';
import { ServiceMultiSelect } from './ServiceMultiSelect';

export function DefaultRestrictions({ data, onSuccess, onError }) {
  const [loading, setLoading] = useState(false);
  const [restrictions, setRestrictions] = useState({
    domains: [],
    entities: [],
    services: []
  });

  // Initialize restrictions from config
  useEffect(() => {
    if (data.config?.default_restrictions) {
      const defaultRestrictions = data.config.default_restrictions;
      setRestrictions({
        domains: Object.keys(defaultRestrictions.domains || {}),
        entities: Object.keys(defaultRestrictions.entities || {}),
        services: Object.keys(defaultRestrictions.services || {})
      });
    }
  }, [data.config]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const auth = await getHAAuth();
      if (!auth) {
        throw new Error('Not authenticated with Home Assistant');
      }

      // Convert restrictions to the expected format
      const defaultRestrictions = {
        domains: {},
        entities: {},
        services: {}
      };

      // Add domain restrictions
      restrictions.domains.forEach(domain => {
        defaultRestrictions.domains[domain] = {
          hide: true,
          services: []
        };
      });

      // Add entity restrictions
      restrictions.entities.forEach(entity => {
        defaultRestrictions.entities[entity] = {
          hide: true,
          services: []
        };
      });

      // Add service restrictions
      restrictions.services.forEach(service => {
        defaultRestrictions.services[service] = {
          hide: true
        };
      });

      const response = await fetch('/api/rbac/config', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${auth.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action: 'update_default_restrictions',
          restrictions: defaultRestrictions
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save default restrictions');
      }

      onSuccess('Default restrictions saved successfully!');
    } catch (error) {
      console.error('Error saving default restrictions:', error);
      onError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const getHAAuth = async () => {
    try {
      // Try to get hass object from Home Assistant context
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
      
      // Try localStorage/sessionStorage
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

  return (
    <div>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 24 }}>
        Configure global restrictions applied to all users.
      </Typography.Paragraph>
      
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <AntMultiSelect
            options={data.domains || []}
            selectedValues={restrictions.domains}
            onSelectionChange={(domains) => setRestrictions(prev => ({ ...prev, domains }))}
            placeholder="Select domains to restrict..."
            disabled={loading}
          />
        </Col>
        
        <Col xs={24} md={12}>
          <AntMultiSelect
            options={data.entities || []}
            selectedValues={restrictions.entities}
            onSelectionChange={(entities) => setRestrictions(prev => ({ ...prev, entities }))}
            placeholder="Select entities to restrict..."
            disabled={loading}
          />
        </Col>
      </Row>
      
      <Space direction="vertical" style={{ width: '100%', marginBottom: 24 }}>
        <ServiceMultiSelect
          domains={data.services?.domains || {}}
          entities={data.services?.entities || {}}
          selectedDomains={restrictions.domains}
          selectedEntities={restrictions.entities}
          selectedServices={restrictions.services}
          onSelectionChange={(services) => setRestrictions(prev => ({ ...prev, services }))}
          placeholder="Select services to block..."
          disabled={loading}
        />
      </Space>
      
      <Space style={{ justifyContent: 'flex-end', display: 'flex', width: '100%' }}>
        <Button
          type="primary"
          onClick={handleSave}
          disabled={loading}
          loading={loading}
          size="large"
        >
          Save Default Restrictions
        </Button>
      </Space>
    </div>
  );
}
