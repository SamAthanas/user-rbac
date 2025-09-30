import { useState, useEffect } from 'preact/hooks';
import {
  Card,
  Typography,
  Button,
  Space,
  Row,
  Col,
  Select,
  Tag
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { AntSingleSelect } from './AntSingleSelect';
import { AntMultiSelect } from './AntMultiSelect';

const { Title, Text } = Typography;
const { Option } = Select;

export function DomainEntityRestrictions({ 
  type, 
  data, 
  restrictions, 
  onRestrictionsChange, 
  disabled = false 
}) {
  const [restrictionRows, setRestrictionRows] = useState([]);

  // Initialize restriction rows from props
  useEffect(() => {
    if (restrictions && restrictions.length > 0) {
      setRestrictionRows(restrictions);
    } else {
      setRestrictionRows([{ [type]: '', services: [] }]);
    }
  }, [restrictions, type]);

  const getAvailableServices = (selectedItem) => {
    if (!selectedItem) return [];
    
    if (type === 'domain') {
      return data.services?.domains?.[selectedItem] || [];
    } else {
      return data.services?.entities?.[selectedItem] || [];
    }
  };

  const handleItemChange = (index, newItem) => {
    const updatedRows = [...restrictionRows];
    updatedRows[index] = { ...updatedRows[index], [type]: newItem, services: [] };
    setRestrictionRows(updatedRows);
    onRestrictionsChange(updatedRows);
  };

  const handleServicesChange = (index, newServices) => {
    const updatedRows = [...restrictionRows];
    updatedRows[index] = { ...updatedRows[index], services: newServices };
    setRestrictionRows(updatedRows);
    onRestrictionsChange(updatedRows);
  };

  const addRow = () => {
    const newRows = [...restrictionRows, { [type]: '', services: [] }];
    setRestrictionRows(newRows);
    onRestrictionsChange(newRows);
  };

  const removeRow = (index) => {
    if (restrictionRows.length > 1) {
      const newRows = restrictionRows.filter((_, i) => i !== index);
      setRestrictionRows(newRows);
      onRestrictionsChange(newRows);
    }
  };

  const getOptions = () => {
    return type === 'domain' ? (data.domains || []) : (data.entities || []);
  };

  const getLabel = () => {
    return type === 'domain' ? 'Domain' : 'Entity';
  };

  return (
    <Card 
      title={`${getLabel()} Restrictions`} 
      style={{ marginBottom: 16 }}
      extra={
        <Button
          type="dashed"
          icon={<PlusOutlined />}
          onClick={addRow}
          disabled={disabled}
          size="small"
        >
          Add {getLabel()}
        </Button>
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {restrictionRows.map((row, index) => (
          <Card 
            key={index} 
            size="small" 
            style={{ backgroundColor: '#fafafa' }}
            extra={
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => removeRow(index)}
                disabled={disabled || restrictionRows.length === 1}
                size="small"
              />
            }
          >
            <Row gutter={[16, 16]} align="middle">
              <Col xs={24} sm={8} md={6}>
                <Text strong>{getLabel()} {index + 1}:</Text>
                <AntSingleSelect
                  options={getOptions()}
                  selectedValue={row[type]}
                  onSelectionChange={(value) => handleItemChange(index, value)}
                  placeholder={`Select ${getLabel().toLowerCase()}...`}
                  disabled={disabled}
                />
              </Col>
              
              <Col xs={24} sm={16} md={18}>
                <Text strong>Services to Block:</Text>
                <AntMultiSelect
                  options={getAvailableServices(row[type])}
                  selectedValues={row.services}
                  onSelectionChange={(services) => handleServicesChange(index, services)}
                  placeholder="Select services to block..."
                  disabled={disabled || !row[type]}
                />
              </Col>
            </Row>
          </Card>
        ))}
      </Space>
    </Card>
  );
}