let isDarkMode = false;

export function initializeTheme() {
    const savedTheme = localStorage.getItem('rbac-theme');
    isDarkMode = savedTheme === 'dark';
    
    applyTheme(isDarkMode);
    
    return isDarkMode;
}

export function getTheme() {
    return isDarkMode;
}

export function applyTheme(darkMode) {
    isDarkMode = darkMode;
    
    const root = document.documentElement;
    
    if (darkMode) {
        root.classList.add('dark-theme');
        root.classList.remove('light-theme');
    } else {
        root.classList.add('light-theme');
        root.classList.remove('dark-theme');
    }
    
    updateMetaThemeColor(darkMode);
}

// Removed filter-based inversion functions - using Ant Design's built-in dark theme instead

export function saveTheme(darkMode) {
    localStorage.setItem('rbac-theme', darkMode ? 'dark' : 'light');
}

function updateMetaThemeColor(darkMode) {
    let metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (!metaThemeColor) {
        metaThemeColor = document.createElement('meta');
        metaThemeColor.name = 'theme-color';
        document.head.appendChild(metaThemeColor);
    }
    
    metaThemeColor.content = darkMode ? '#2a2a2a' : '#ffffff';
}

export function watchSystemTheme(callback) {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = (e) => {
        const savedTheme = localStorage.getItem('rbac-theme');
        if (!savedTheme) {
            callback(e.matches);
        }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    
    // Return cleanup function
    return () => mediaQuery.removeEventListener('change', handleChange);
}

// Initialize theme on module load
initializeTheme();
