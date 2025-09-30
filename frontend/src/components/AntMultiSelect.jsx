import { useState } from 'preact/hooks';
import { Select, Tag } from 'antd';

const { Option } = Select;

export function AntMultiSelect({ 
  options, 
  selectedValues, 
  onSelectionChange, 
  placeholder = "Select items...",
  disabled = false 
}) {
  const handleChange = (value) => {
    onSelectionChange(value || []);
  };

  const tagRender = (props) => {
    const { label, closable, onClose } = props;
    return (
      <Tag
        color="blue"
        closable={closable}
        onClose={onClose}
        style={{ marginRight: 3 }}
      >
        {label}
      </Tag>
    );
  };

  return (
    <Select
      mode="multiple"
      placeholder={placeholder}
      value={selectedValues}
      onChange={handleChange}
      disabled={disabled}
      tagRender={tagRender}
      style={{ width: '100%' }}
      showSearch
      filterOption={(input, option) =>
        option?.children?.toLowerCase().indexOf(input.toLowerCase()) >= 0
      }
    >
      {options.map((option) => (
        <Option key={option} value={option}>
          {option}
        </Option>
      ))}
    </Select>
  );
}
