import { useState } from 'preact/hooks';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  OutlinedInput
} from '@mui/material';

export function MaterialSingleSelect({ 
  options, 
  selectedValue, 
  onSelectionChange, 
  label, 
  placeholder = "Select an item...",
  disabled = false 
}) {
  const handleChange = (event) => {
    onSelectionChange(event.target.value);
  };

  return (
    <FormControl fullWidth disabled={disabled}>
      <InputLabel id={`singleselect-label-${label}`}>{label}</InputLabel>
      <Select
        labelId={`singleselect-label-${label}`}
        value={selectedValue || ''}
        onChange={handleChange}
        input={<OutlinedInput label={label} />}
        displayEmpty
      >
        <MenuItem value="">
          <em>{placeholder}</em>
        </MenuItem>
        {options.map((option) => (
          <MenuItem key={option} value={option}>
            {option}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
