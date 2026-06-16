// RBAC Frontend JavaScript Blocker
// Restricts access to entities and services in the quick-bar based on the user's role

(function() {
    'use strict';
    
    console.log('🔒 RBAC frontend script loaded');
    
    let blockConfig = {
        domains: [],
        entities: [],
        services: [],
        allowed_domains: [],
        allowed_entities: []
    };
    let frontendBlockingEnabled = false;
    let patched = false;
    
    // Function to get the hass object
    function getHassObject() {
        try {
            // Try to get hass from the home-assistant element
            const homeAssistantElement = document.querySelector("home-assistant");
            if (homeAssistantElement && homeAssistantElement.hass) {
                return homeAssistantElement.hass;
            }
            
            // Fallback to window.hass
            if (window.hass) {
                return window.hass;
            }
            
            return null;
        } catch (error) {
            console.error('RBAC: Error getting hass object:', error);
            return null;
        }
    }
    
    // Function to fetch blocking configuration from API
    async function fetchBlockingConfig() {
        try {
            const hass = getHassObject();
            if (!hass) {
                console.error('RBAC: No hass object available');
                return false;
            }
            
            // Get the base URL for API calls
            const baseUrl = hass.config.external_url || hass.config.internal_url || window.location.origin;
            
            // Make HTTP request to the frontend blocking API
            const response = await fetch(`${baseUrl}/api/rbac/frontend-blocking`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${hass.auth.accessToken}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            if (data && data.enabled) {
                blockConfig = {
                    deny_all: Boolean(data.deny_all),
                    domains: data.domains || [],
                    entities: data.entities || [],
                    services: data.services || [],
                    allowed_domains: data.allowed_domains || [],
                    allowed_entities: data.allowed_entities || []
                };

                const hasRestrictions = blockConfig.deny_all
                    || blockConfig.entities.length > 0
                    || blockConfig.domains.length > 0
                    || blockConfig.allowed_entities.length > 0
                    || blockConfig.allowed_domains.length > 0;

                if (hasRestrictions) {
                    console.log('🔒 RBAC Blocking config loaded');
                    console.log(`   - Blocked: ${blockConfig.domains.length} domains, ${blockConfig.entities.length} entities`);
                    console.log(`   - Allowed: ${blockConfig.allowed_domains.length} domains, ${blockConfig.allowed_entities.length} entities`);
                    return true;
                }
            }

            console.log('🔓 RBAC Frontend blocking disabled or no restrictions for this user');
            blockConfig = {
                deny_all: false,
                domains: [],
                entities: [],
                services: [],
                allowed_domains: [],
                allowed_entities: []
            };
            return false;
        } catch (error) {
            console.error('RBAC: Error fetching blocking config:', error);
            // Fallback to empty config on error
            blockConfig = {
                deny_all: false,
                domains: [],
                entities: [],
                services: [],
                allowed_domains: [],
                allowed_entities: []
            };
            return false;
        }
    }
    
    // Function to check if an entity should be blocked
    function isEntityBlocked(entityId) {
        if (!frontendBlockingEnabled) {
            return false;
        }
        
        // First check if entity is explicitly allowed
        if (blockConfig.allowed_entities.includes(entityId)) {
            return false;
        }
        
        // Check if domain is explicitly allowed
        const domain = entityId.split('.')[0];
        if (blockConfig.allowed_domains.includes(domain)) {
            return false;
        }
        
        // Check if entity is explicitly blocked
        if (blockConfig.entities.includes(entityId)) {
            return true;
        }
        
        // Check if domain is blocked
        if (blockConfig.domains.includes(domain)) {
            return true;
        }

        // deny_all roles: block everything not explicitly allowed
        if (blockConfig.deny_all) {
            return true;
        }
        
        return false;
    }
    
    // Function to check if a service should be blocked
    function isServiceBlocked(service) {
        if (!frontendBlockingEnabled || !service) {
            return false;
        }
        
        // Check if service is explicitly blocked
        return blockConfig.services.some(blockedService => service.includes(blockedService));
    }
    
    // Function to patch Quick Bar
    function patchQuickBar() {
        customElements.whenDefined("ha-quick-bar").then(() => {
            const proto = customElements.get("ha-quick-bar").prototype;
            
            // Patch _generateEntityItems
            const origGenerateEntities = proto._generateEntityItems;
            proto._generateEntityItems = async function () {
                const allEntities = await origGenerateEntities.call(this);
                
                if (!frontendBlockingEnabled) {
                    return allEntities;
                }
                
                const filtered = allEntities.filter(e => {
                    const blocked = isEntityBlocked(e.entityId);
                    if (blocked) {
                        return false;
                    }
                    return true;
                });
                
                if (filtered.length !== allEntities.length) {
                    const totalFiltered = allEntities.length - filtered.length;
                    console.log(`🔒 Quick Bar: Filtered ${totalFiltered} entities`);
                }
                return filtered;
            };
            
            // Patch _generateReloadCommands
            const origGenerateReload = proto._generateReloadCommands;
            proto._generateReloadCommands = async function () {
                const allCommands = await origGenerateReload.call(this);
                
                if (!frontendBlockingEnabled) {
                    return allCommands;
                }
                
                const filtered = allCommands.filter(c => {
                    // Keep only commands whose service is NOT blocked
                    const service = c.action?.toString();
                    if (!service) return true; // keep navigation commands
                    
                    if (isServiceBlocked(service)) {
                        return false;
                    }
                    return true;
                });
                
                if (filtered.length !== allCommands.length) {
                    console.log(
                        `🔒 Quick Bar: Filtered ${allCommands.length - filtered.length} reload commands`
                    );
                }
                return filtered;
            };
            
            // Patch _generateServerControlCommands
            const origGenerateServerControl = proto._generateServerControlCommands;
            proto._generateServerControlCommands = function () {
                const allCommands = origGenerateServerControl.call(this);
                
                if (!frontendBlockingEnabled) {
                    return allCommands;
                }
                
                const filtered = allCommands.filter(c => {
                    const service = c.action?.toString();
                    if (!service) return true;
                    
                    if (isServiceBlocked(service)) {
                        return false;
                    }
                    return true;
                });
                
                if (filtered.length !== allCommands.length) {
                    console.log(
                        `🔒 Quick Bar: Filtered ${allCommands.length - filtered.length} server control commands`
                    );
                }
                return filtered;
            };
            
            // Clear cached items on dialog open
            const origShowDialog = proto.showDialog;
            proto.showDialog = async function (params) {
                this._entityItems = undefined;
                this._commandItems = undefined;
                return origShowDialog.call(this, params);
            };
            
            console.log("✅ Quick Bar patched");
        });
    }
    
    // Function to patch entity search and filtering
    function patchEntitySearch() {
        // Patch states.get
        const hass = getHassObject();
        if (hass && hass.states && hass.states.get) {
            const originalStatesGet = hass.states.get.bind(hass.states);

            hass.states.get = function(entityId) {
                const result = originalStatesGet(entityId);
                
                // If frontend blocking is enabled and entity is blocked, return null
                if (frontendBlockingEnabled && result && isEntityBlocked(entityId)) {
                        return null;
                }
                
                return result;
            };
            
        }
        
        // Patch states.async_all
        if (hass && hass.states && hass.states.async_all) {
            const originalStatesAsyncAll = hass.states.async_all.bind(hass.states);
            
            hass.states.async_all = function(domainFilter) {
                const result = originalStatesAsyncAll(domainFilter);
                
                if (!frontendBlockingEnabled) {
                    return result;
                }
                
                // Filter out blocked entities
                    const filteredResult = result.filter(state => {
                    if (isEntityBlocked(state.entity_id)) {
                            return false;
                        }
                        return true;
                    });
                    
                    return filteredResult;
            };
            
        }
    }
    
    // Function to initialize RBAC
    async function initializeRBAC() {
        if (patched) {
            return; // Already initialized
        }
        
        try {
            // Load per-user blocking config from the RBAC API
            frontendBlockingEnabled = await fetchBlockingConfig();
            
            if (!frontendBlockingEnabled) {
                console.log('🔓 RBAC Frontend blocking disabled');
                patched = true; // Mark as patched to prevent re-initialization
                return;
            }
            
            // Apply patches
            patchQuickBar();
            patchEntitySearch();
            
            patched = true;
            console.log('✅ RBAC initialized');
            
        } catch (error) {
            console.error('RBAC: Error during initialization:', error);
        }
    }
    
    // Function to reinitialize when hass updates
    function setupHassUpdateListener() {
        // Blocking config is loaded once on startup via the RBAC API.
    }
    
    // Initialize when DOM is ready
    function startInitialization() {
        const hass = getHassObject();
        if (hass && hass.states && hass.connection) {
            initializeRBAC();
            setupHassUpdateListener();
        } else {
            // Wait for Home Assistant to be ready
            setTimeout(startInitialization, 100);
        }
    }
    
    // Start initialization when the script loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startInitialization);
    } else {
        startInitialization();
    }
    
    // Also listen for hass updates
    if (window.hass) {
        const originalUpdateHass = window.hass.updateHass;
        if (originalUpdateHass) {
            window.hass.updateHass = function(newHass) {
                const result = originalUpdateHass.call(this, newHass);
                // Re-initialize if not already patched
                if (!patched) {
                    setTimeout(startInitialization, 100);
                }
                return result;
            };
        }
    }
    
    // Monitor for Home Assistant object changes
    let hassCheckInterval = setInterval(() => {
        if (!patched) {
            const hass = getHassObject();
            if (hass && hass.states && hass.connection) {
                startInitialization();
            }
        } else {
            clearInterval(hassCheckInterval);
        }
    }, 500);
    
    // Stop checking after 10 seconds
    setTimeout(() => {
        clearInterval(hassCheckInterval);
        if (!patched) {
            console.log('RBAC: Timeout reached, stopping initialization attempts');
        }
    }, 10000);
    
    console.log('🔒 RBAC frontend script initialized');
})();
