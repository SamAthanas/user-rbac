// RBAC Frontend JavaScript Blocker
// Restricts access to entities and services in the quick-bar based on the user's role

(function() {
    'use strict';
    
    console.log('🔒 RBAC frontend script loaded (new architecture)');
    
    let blockConfig = {
        domains: [],
        entities: [],
        services: []
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
    
    // Function to check if frontend blocking is enabled via sensor
    function checkFrontendBlockingEnabled() {
        try {
            const hass = getHassObject();
            if (!hass || !hass.states) {
                return false;
            }
            
            // Check the RBAC frontend blocking sensor
            const sensorState = hass.states['sensor.rbac_frontend_blocking'];
            if (sensorState && sensorState.state === 'on') {
                console.log('🔒 RBAC Frontend Blocking is ENABLED');
                return true;
            } else {
                console.log('🔓 RBAC Frontend Blocking is DISABLED');
                return false;
            }
        } catch (error) {
            console.error('RBAC: Error checking frontend blocking sensor:', error);
            return false;
        }
    }
    
    // Function to fetch blocking configuration from API
    async function fetchBlockingConfig() {
        try {
            const hass = getHassObject();
            if (!hass) {
                console.error('RBAC: No hass object available');
                return;
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
                    domains: data.domains || [],
                    entities: data.entities || [],
                    services: data.services || []
                };
                
                console.log('🔒 RBAC Blocking config loaded:', blockConfig);
                console.log(`   - Blocked domains: ${blockConfig.domains.length}`);
                console.log(`   - Blocked entities: ${blockConfig.entities.length}`);
                console.log(`   - Blocked services: ${blockConfig.services.length}`);
            } else {
                console.log('🔓 RBAC Frontend blocking disabled or no restrictions');
                blockConfig = {
                    domains: [],
                    entities: [],
                    services: []
                };
            }
        } catch (error) {
            console.error('RBAC: Error fetching blocking config:', error);
            // Fallback to empty config on error
            blockConfig = {
                domains: [],
                entities: [],
                services: []
            };
        }
    }
    
    // Function to check if an entity should be blocked
    function isEntityBlocked(entityId) {
        if (!frontendBlockingEnabled) {
            return false;
        }
        
        // Check if entity is explicitly blocked
        if (blockConfig.entities.includes(entityId)) {
            return true;
        }
        
        // Check if domain is blocked
        const domain = entityId.split('.')[0];
        if (blockConfig.domains.includes(domain)) {
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
                    if (isEntityBlocked(e.entityId)) {
                        return false;
                    }
                    return true;
                });
                
                if (filtered.length !== allEntities.length) {
                    console.log(
                        `🔒 Quick Bar: Filtered ${allEntities.length - filtered.length} entities`
                    );
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
            // Check if frontend blocking is enabled
            frontendBlockingEnabled = checkFrontendBlockingEnabled();
            
            if (!frontendBlockingEnabled) {
                console.log('🔓 RBAC Frontend blocking disabled');
                patched = true; // Mark as patched to prevent re-initialization
                return;
            }
            
            // Fetch blocking configuration
            await fetchBlockingConfig();
            
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
        const hass = getHassObject();
        if (hass && hass.connection) {
            // Listen for state changes, particularly the RBAC sensor
            hass.connection.subscribeEvents((event) => {
                if (event.data && event.data.entity_id === 'sensor.rbac_frontend_blocking') {
                    console.log('🔒 RBAC sensor changed, reinitializing...');
                    patched = false; // Allow re-initialization
                    setTimeout(initializeRBAC, 100);
                }
            }, 'state_changed');
            
        }
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
    
    console.log('🔒 RBAC frontend script initialized (new architecture)');
})();