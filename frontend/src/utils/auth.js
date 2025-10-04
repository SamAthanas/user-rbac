/**
 * Shared authentication utilities for Home Assistant integration
 */

/**
 * Get the Home Assistant object from various contexts
 * @returns {Object|null} The hass object or null if not found
 */
export const getHassObject = () => {
  try {
    const homeAssistantElement = document.querySelector("home-assistant");
    if (homeAssistantElement && homeAssistantElement.hass) {
      return homeAssistantElement.hass;
    }
    if (window.hass) {
      return window.hass;
    }
    if (window.parent && window.parent !== window && window.parent.hass) {
      return window.parent.hass;
    }
    return null;
  } catch (error) {
    console.error('Error getting hass object:', error);
    return null;
  }
};

/**
 * Get authentication token for Home Assistant API calls
 * @returns {Promise<Object|null>} Auth object with access_token and token_type, or null if not authenticated
 */
export const getHAAuth = async () => {
  try {
    // Try to get hass object from Home Assistant context
    const hass = getHassObject();
    if (hass && hass.auth) {
      if (hass.auth.data && hass.auth.data.access_token) {
        return {
          access_token: hass.auth.data.access_token,
          token_type: 'Bearer'
        };
      }
      if (hass.auth.access_token) {
        return {
          access_token: hass.auth.access_token,
          token_type: 'Bearer'
        };
      }
    }
    
    // Try to get from localStorage (if available)
    const auth = localStorage.getItem('hassTokens');
    if (auth) {
      const tokens = JSON.parse(auth);
      return {
        access_token: tokens.access_token,
        token_type: 'Bearer'
      };
    }
    
    // Try to get from sessionStorage
    const sessionAuth = sessionStorage.getItem('hassTokens');
    if (sessionAuth) {
      const tokens = JSON.parse(sessionAuth);
      return {
        access_token: tokens.access_token,
        token_type: 'Bearer'
      };
    }
    
    // Fallback: try to get auth from the current page context
    const response = await fetch('/auth/token');
    if (!response.ok) {
      throw new Error('Not authenticated');
    }
    return await response.json();
  } catch (error) {
    console.error('Error getting HA auth:', error);
    return null;
  }
};

/**
 * Make an authenticated API call to Home Assistant
 * @param {string} url - The API endpoint URL
 * @param {Object} options - Fetch options (method, body, etc.)
 * @returns {Promise<Response>} The fetch response
 */
export const makeAuthenticatedRequest = async (url, options = {}) => {
  const auth = await getHAAuth();
  if (!auth) {
    throw new Error('Not authenticated with Home Assistant');
  }

  const defaultOptions = {
    headers: {
      'Authorization': `Bearer ${auth.access_token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  };

  return fetch(url, { ...defaultOptions, ...options });
};
