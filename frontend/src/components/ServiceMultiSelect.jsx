import { useState, useEffect } from 'preact/hooks';
import { AntMultiSelect } from './AntMultiSelect';

export function ServiceMultiSelect({ 
  domains, 
  entities, 
  selectedDomains, 
  selectedEntities, 
  selectedServices, 
  onSelectionChange, 
  placeholder = "Select services to block...",
  disabled = false 
}) {
  const [availableServices, setAvailableServices] = useState([]);

  useEffect(() => {
    // Get services for selected domains and entities
    const domainServices = selectedDomains.flatMap(domain => 
      domains[domain] || []
    );
    
    const entityServices = selectedEntities.flatMap(entity => 
      entities[entity] || []
    );
    
    // Combine and deduplicate services
    const allServices = [...new Set([...domainServices, ...entityServices])];
    setAvailableServices(allServices);
  }, [selectedDomains, selectedEntities, domains, entities]);

  return (
    <AntMultiSelect
      options={availableServices}
      selectedValues={selectedServices}
      onSelectionChange={onSelectionChange}
      placeholder={placeholder}
      disabled={disabled}
    />
  );
}
