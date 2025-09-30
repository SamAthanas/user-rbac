// RBAC Frontend JavaScript
// Override entity search functions to provide user context

(function() {
    'use strict';
    
    console.log('RBAC frontend script loaded');
    
    // Store original functions
    let originalStatesGet = null;
    let originalStatesAsyncAll = null;
    let originalWebSocketSend = null;
    let originalWebSocketSendPromise = null;
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
    
    // Function to get current user ID
    function getCurrentUserId() {
        try {
            const hass = getHassObject();
            if (!hass) {
                console.log('RBAC: No hass object available');
                return null;
            }
            
            // Try to get user from Home Assistant's auth system
            if (hass.auth && hass.auth.currentUser) {
                return hass.auth.currentUser.id;
            }
            
            // Try to get user from the user object
            if (hass.user && hass.user.id) {
                return hass.user.id;
            }
            
            // Try to get user from the store
            if (hass.store && hass.store.state) {
                const state = hass.store.state;
                if (state.auth && state.auth.currentUser) {
                    return state.auth.currentUser.id;
                }
            }
            
            console.log('RBAC: Could not determine current user ID');
            return null;
        } catch (error) {
            console.error('RBAC: Error getting current user ID:', error);
            return null;
        }
    }
    
    // Function to patch WebSocket connection
    function patchWebSocket() {
        const hass = getHassObject();
        if (hass && hass.connection) {
            let sendPatched = false;
            let sendPromisePatched = false;
            
            // Patch sendMessage
            if (hass.connection.sendMessage && !originalWebSocketSend) {
                originalWebSocketSend = hass.connection.sendMessage.bind(hass.connection);
                
                hass.connection.sendMessage = function(message, callback) {
                    // Log WebSocket messages for debugging
                    if (message && message.type) {
                        const userId = getCurrentUserId();
                        
                        // Log specific message types for testing
                        const testMessageTypes = [
                            'frontend/get_icons',
                            'frontend/get_translations',
                            'config/device_registry/list',
                            'config/entity_registry/list',
                            'get_states'
                        ];
                        
                        if (testMessageTypes.includes(message.type)) {
                            console.log(`RBAC: WebSocket ${message.type} by user: ${userId}`);
                        }
                        
                        // Log specific message types we're interested in
                        if (message.type === 'subscribe_events' && message.event_type === 'state_changed') {
                            console.log('RBAC: Intercepting state_changed subscription');
                        }
                        
                        if (message.type === 'get_states') {
                            console.log('RBAC: Intercepting get_states request');
                        }
                        
                        if (message.type === 'search') {
                            console.log('RBAC: Intercepting search request');
                        }
                        
                        if (message.type === 'config/device_registry/list') {
                            console.log('RBAC: Intercepting device registry list request');
                        }
                        
                        if (message.type === 'config/entity_registry/list') {
                            console.log('RBAC: Intercepting entity registry list request');
                        }
                    }
                    
                    // Call original function
                    return originalWebSocketSend(message, callback);
                };
                
                console.log('RBAC: Patched WebSocket sendMessage');
                sendPatched = true;
            }
            
            // Patch sendMessagePromise
            if (hass.connection.sendMessagePromise && !originalWebSocketSendPromise) {
                originalWebSocketSendPromise = hass.connection.sendMessagePromise.bind(hass.connection);
                
                hass.connection.sendMessagePromise = function(message) {
                    // Log WebSocket messages for debugging
                    if (message && message.type) {
                        const userId = getCurrentUserId();
                        
                        // Log specific message types for testing
                        const testMessageTypes = [
                            'frontend/get_icons',
                            'frontend/get_translations',
                            'config/device_registry/list',
                            'config/entity_registry/list',
                            'get_states'
                        ];
                        
                        if (testMessageTypes.includes(message.type)) {
                            console.log(`RBAC: WebSocket Promise ${message.type} by user: ${userId}`);
                        }
                        
                        // Log specific message types we're interested in
                        if (message.type === 'subscribe_events' && message.event_type === 'state_changed') {
                            console.log('RBAC: Intercepting state_changed subscription (Promise)');
                        }
                        
                        if (message.type === 'get_states') {
                            console.log('RBAC: Intercepting get_states request (Promise)');
                        }
                        
                        if (message.type === 'search') {
                            console.log('RBAC: Intercepting search request (Promise)');
                        }
                        
                        if (message.type === 'config/device_registry/list') {
                            console.log('RBAC: Intercepting device registry list request (Promise)');
                        }
                        
                        if (message.type === 'config/entity_registry/list') {
                            console.log('RBAC: Intercepting entity registry list request (Promise)');
                        }
                    }
                    
                    // Call original function
                    return originalWebSocketSendPromise(message);
                };
                
                console.log('RBAC: Patched WebSocket sendMessagePromise');
                sendPromisePatched = true;
            }
            
            return sendPatched || sendPromisePatched;
        }
        return false;
    }
    
    
    // Function to patch states.get
    function patchStatesGet() {
        const hass = getHassObject();
        if (hass && hass.states && hass.states.get && !originalStatesGet) {
            originalStatesGet = hass.states.get.bind(hass.states);

            console.log('RBAC: Patched states.get');
            hass.states.get = function(entityId) {
                const userId = getCurrentUserId();
                console.log(`RBAC: states.get(${entityId}) called by user: ${userId}`);
                
                // Call original function
                const result = originalStatesGet(entityId);
                
                // If we have a user ID and the entity should be hidden, return null
                if (userId && result) {
                    // Check if this entity should be hidden for this user
                    // This is a simple check - in a real implementation, you'd want to
                    // make an API call to check the RBAC configuration
                    const domain = entityId.split('.')[0];
                    const hiddenDomains = ['light', 'homeassistant', 'system_log', 'hassio'];
                    
                    if (hiddenDomains.includes(domain)) {
                        console.log(`RBAC: Hiding entity ${entityId} for user ${userId} (domain: ${domain})`);
                        return null;
                    }
                }
                
                return result;
            };
            
            console.log('RBAC: Patched states.get');
            return true;
        }
        return false;
    }
    
    // Function to patch states.async_all
    function patchStatesAsyncAll() {
        const hass = getHassObject();
        if (hass && hass.states && hass.states.async_all && !originalStatesAsyncAll) {
            originalStatesAsyncAll = hass.states.async_all.bind(hass.states);

            console.log('RBAC: Patched states.async_all');
            hass.states.async_all = function(domainFilter) {
                const userId = getCurrentUserId();
                console.log(`RBAC: states.async_all(${domainFilter}) called by user: ${userId}`);
                
                // Call original function
                const result = originalStatesAsyncAll(domainFilter);
                
                // If we have a user ID, filter the results
                if (userId && result) {
                    const hiddenDomains = ['light', 'homeassistant', 'system_log', 'hassio'];
                    const filteredResult = result.filter(state => {
                        const domain = state.entity_id.split('.')[0];
                        if (hiddenDomains.includes(domain)) {
                            console.log(`RBAC: Filtering out entity ${state.entity_id} for user ${userId} (domain: ${domain})`);
                            return false;
                        }
                        return true;
                    });
                    
                    console.log(`RBAC: Filtered ${result.length} entities to ${filteredResult.length} for user ${userId}`);
                    return filteredResult;
                }
                
                return result;
            };
            
            console.log('RBAC: Patched states.async_all');
            return true;
        }
        return false;
    }
    
    // Function to patch when Home Assistant is ready
    function patchWhenReady() {
        if (patched) {
            return; // Already patched, don't try again
        }
        
        const hass = getHassObject();
        if (hass && hass.states && hass.connection) {
            const getPatched = patchStatesGet();
            const asyncAllPatched = patchStatesAsyncAll();
            const webSocketPatched = patchWebSocket();
            
            if (getPatched && asyncAllPatched && webSocketPatched) {
                patched = true;
                console.log('RBAC: All patches applied successfully');
            }
        } else {
            // Wait for Home Assistant to be ready
            setTimeout(patchWhenReady, 100);
        }
    }
    
    // Start patching when the script loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', patchWhenReady);
    } else {
        patchWhenReady();
    }
    
    // Also patch when Home Assistant updates
    if (window.hass) {
        const originalUpdateHass = window.hass.updateHass;
        if (originalUpdateHass) {
            window.hass.updateHass = function(newHass) {
                const result = originalUpdateHass.call(this, newHass);
                // Re-patch after update if not already patched
                if (!patched) {
                    setTimeout(() => {
                        patchWhenReady();
                    }, 100);
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
                patchWhenReady();
            }
        } else {
            clearInterval(hassCheckInterval);
        }
    }, 500);
    
    // Stop checking after 10 seconds
    setTimeout(() => {
        clearInterval(hassCheckInterval);
        if (!patched) {
            console.log('RBAC: Timeout reached, stopping patch attempts');
        }
    }, 10000);
    
    console.log('RBAC frontend script initialized');
})();