import { useState } from 'preact/hooks';
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  OutlinedInput,
  Box,
  Checkbox,
  ListItemText
} from '@mui/material';

export function MaterialMultiSelect({ 
  options, 
  selectedValues, 
  onSelectionChange, 
  label, 
  placeholder = "Select items...",
  disabled = false 
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleChange = (event) => {
    const value = event.target.value;
    onSelectionChange(typeof value === 'string' ? value.split(',') : value);
  };

  return (
    <FormControl fullWidth disabled={disabled}>
      <InputLabel id={`multiselect-label-${label}`}>{label}</InputLabel>
      <Select
        labelId={`multiselect-label-${label}`}
        multiple
        value={selectedValues}
        onChange={handleChange}
        input={<OutlinedInput label={label} />}
        renderValue={(selected) => (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {selected.map((value) => (
              <Chip key={value} label={value} size="small" />
            ))}
          </Box>
        )}
        open={isOpen}
        onOpen={() => setIsOpen(true)}
        onClose={() => setIsOpen(false)}
      >
        {options.map((option) => (
          <MenuItem key={option} value={option}>
            <Checkbox checked={selectedValues.indexOf(option) > -1} />
            <ListItemText primary={option} />
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
