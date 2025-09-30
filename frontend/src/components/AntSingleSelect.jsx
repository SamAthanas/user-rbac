import { Select } from 'antd';

const { Option } = Select;

export function AntSingleSelect({ 
  options, 
  selectedValue, 
  onSelectionChange, 
  placeholder = "Select an item...",
  disabled = false 
}) {
  const handleChange = (value) => {
    onSelectionChange(value);
  };

  return (
    <Select
      placeholder={placeholder}
      value={selectedValue || undefined}
      onChange={handleChange}
      disabled={disabled}
      style={{ width: '100%' }}
      showSearch
      filterOption={(input, option) =>
        option?.children?.toLowerCase().indexOf(input.toLowerCase()) >= 0
      }
      allowClear
    >
      {options.map((option) => (
        <Option key={option} value={option}>
          {option}
        </Option>
      ))}
    </Select>
  );
}
