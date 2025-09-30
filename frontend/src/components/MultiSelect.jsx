import { useState, useEffect } from 'preact/hooks';

export function MultiSelect({ 
  options, 
  selectedValues, 
  onSelectionChange, 
  placeholder = "Select items...",
  disabled = false 
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const filteredOptions = options.filter(option =>
    option.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleToggle = (value) => {
    if (disabled) return;
    
    const newSelection = selectedValues.includes(value)
      ? selectedValues.filter(v => v !== value)
      : [...selectedValues, value];
    
    onSelectionChange(newSelection);
  };

  const handleRemove = (value) => {
    if (disabled) return;
    
    const newSelection = selectedValues.filter(v => v !== value);
    onSelectionChange(newSelection);
  };

  return (
    <div style="position: relative; width: 100%;">
      {/* Selected items display */}
      <div 
        style="
          min-height: 36px;
          padding: 8px 12px;
          border: 1px solid #e0e0e0;
          border-radius: 4px;
          background: white;
          cursor: pointer;
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          align-items: center;
        "
        onClick={() => !disabled && setIsOpen(!isOpen)}
      >
        {selectedValues.length === 0 ? (
          <span style="color: #999; font-size: 13px;">{placeholder}</span>
        ) : (
          selectedValues.map(value => (
            <span 
              key={value}
              style="
                background: #e3f2fd;
                color: #1976d2;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 4px;
              "
            >
              {value}
              {!disabled && (
                <span 
                  style="cursor: pointer; font-weight: bold;"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemove(value);
                  }}
                >
                  ×
                </span>
              )}
            </span>
          ))
        )}
        <span style="margin-left: auto; color: #666;">▼</span>
      </div>

      {/* Dropdown options */}
      {isOpen && !disabled && (
        <div 
          style="
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #e0e0e0;
            border-top: none;
            border-radius: 0 0 4px 4px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
          "
        >
          {/* Search input */}
          <input
            type="text"
            placeholder="Search..."
            value={searchTerm}
            onInput={(e) => setSearchTerm(e.target.value)}
            style="
              width: 100%;
              padding: 8px 12px;
              border: none;
              border-bottom: 1px solid #e0e0e0;
              outline: none;
              font-size: 13px;
            "
          />
          
          {/* Options */}
          {filteredOptions.map(option => (
            <div
              key={option}
              style="
                padding: 8px 12px;
                cursor: pointer;
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 8px;
                background: ${selectedValues.includes(option) ? '#f0f8ff' : 'white'};
              "
              onClick={() => handleToggle(option)}
            >
              <input
                type="checkbox"
                checked={selectedValues.includes(option)}
                readOnly
                style="margin: 0;"
              />
              {option}
            </div>
          ))}
          
          {filteredOptions.length === 0 && (
            <div style="padding: 8px 12px; color: #999; font-size: 13px;">
              No options found
            </div>
          )}
        </div>
      )}
    </div>
  );
}
