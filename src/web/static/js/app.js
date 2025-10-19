/**
 * File Categorizer Web Interface JavaScript
 * Main application logic and utilities
 */

// Global application state
const App = {
    config: {
        apiBaseUrl: '/api',
        defaultPageSize: 50,
        maxRetries: 3
    },
    state: {
        currentScan: null,
        currentCleanup: null,
        eventSource: null
    }
};

// Utility functions
const Utils = {
    /**
     * Format file size in human readable format
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    /**
     * Format date in local format
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    },

    /**
     * Get category badge HTML
     */
    getCategoryBadge(category) {
        const badges = {
            'graphics': '<span class="badge category-badge category-graphics">Graphics</span>',
            'lightburn': '<span class="badge category-badge category-lightburn">LightBurn</span>',
            'vector': '<span class="badge category-badge category-vector">Vector</span>'
        };
        return badges[category] || '<span class="badge bg-secondary">Unknown</span>';
    },

    /**
     * Get category icon
     */
    getCategoryIcon(category) {
        const icons = {
            'graphics': 'bi-image',
            'lightburn': 'bi-lightning',
            'vector': 'bi-vector-pen'
        };
        return icons[category] || 'bi-file';
    },

    /**
     * Show toast notification
     */
    showToast(message, type = 'info') {
        // Create toast element
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                            data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        // Add to toast container (create if doesn't exist)
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '1055';
            document.body.appendChild(container);
        }
        
        container.insertAdjacentHTML('beforeend', toastHtml);
        
        // Show toast
        const toastElement = container.lastElementChild;
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
        
        // Remove from DOM after hiding
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    },

    /**
     * Show loading state
     */
    showLoading(element, message = 'Loading...') {
        const loadingHtml = `
            <div class="loading-overlay">
                <div class="text-center">
                    <div class="spinner-border text-primary mb-2" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="text-muted">${message}</div>
                </div>
            </div>
        `;
        
        element.style.position = 'relative';
        element.insertAdjacentHTML('beforeend', loadingHtml);
    },

    /**
     * Hide loading state
     */
    hideLoading(element) {
        const overlay = element.querySelector('.loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    },

    /**
     * Debounce function calls
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// API helper functions
const API = {
    /**
     * Make API request with error handling
     */
    async request(endpoint, options = {}) {
        const url = `${App.config.apiBaseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('API request failed:', error);
            
            // Don't show toast for expected errors during initialization
            const suppressToast = options.suppressToast || 
                                endpoint.includes('/health') || 
                                endpoint.includes('/files/stats') || 
                                endpoint.includes('/files/recent') ||
                                endpoint.includes('/scan/status') ||
                                endpoint.includes('/cleanup/status');
            
            if (!suppressToast) {
                Utils.showToast(`API Error: ${error.message}`, 'danger');
            }
            
            throw error;
        }
    },

    /**
     * GET request
     */
    async get(endpoint, params = {}) {
        // Construct URL manually to avoid issues
        let url = `${App.config.apiBaseUrl}/${endpoint}`;
        
        // Add query parameters if any
        if (params && Object.keys(params).length > 0) {
            const searchParams = new URLSearchParams();
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                    searchParams.append(key, params[key]);
                }
            });
            if (searchParams.toString()) {
                url += `?${searchParams.toString()}`;
            }
        }
        
        console.log('API GET URL:', url); // Debug log
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        try {
            const response = await fetch(url, defaultOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('API GET request failed:', error);
            
            // Don't show toast for expected errors during initialization
            const suppressToast = endpoint.includes('health') || 
                                endpoint.includes('files/stats') || 
                                endpoint.includes('files/recent') ||
                                endpoint.includes('scan/status') ||
                                endpoint.includes('cleanup/status');
            
            if (!suppressToast) {
                Utils.showToast(`API Error: ${error.message}`, 'danger');
            }
            
            throw error;
        }
    },

    /**
     * POST request
     */
    async post(endpoint, data = {}) {
        const url = `${App.config.apiBaseUrl}/${endpoint}`;
        console.log('API POST URL:', url); // Debug log
        
        const options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        };
        
        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('API POST request failed:', error);
            Utils.showToast(`API Error: ${error.message}`, 'danger');
            throw error;
        }
    },

    /**
     * DELETE request
     */
    async delete(endpoint) {
        const url = `${App.config.apiBaseUrl}/${endpoint}`;
        console.log('API DELETE URL:', url); // Debug log
        
        const options = {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        };
        
        try {
            const response = await fetch(url, options);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();
        } catch (error) {
            console.error('API DELETE request failed:', error);
            Utils.showToast(`API Error: ${error.message}`, 'danger');
            throw error;
        }
    }
};

// Table helper functions
const TableUtils = {
    /**
     * Create sortable table header
     */
    createSortableHeader(text, sortKey, currentSort = {}) {
        const isActive = currentSort.key === sortKey;
        const direction = isActive ? currentSort.direction : 'asc';
        const nextDirection = isActive && direction === 'asc' ? 'desc' : 'asc';
        
        const icon = isActive 
            ? (direction === 'asc' ? 'bi-sort-up' : 'bi-sort-down')
            : 'bi-sort';
        
        return `
            <th class="cursor-pointer" data-sort="${sortKey}" data-direction="${nextDirection}">
                ${text} <i class="bi ${icon}"></i>
            </th>
        `;
    },

    /**
     * Sort table data
     */
    sortData(data, sortKey, direction = 'asc') {
        return [...data].sort((a, b) => {
            let aVal = a[sortKey];
            let bVal = b[sortKey];
            
            // Handle different data types
            if (typeof aVal === 'string') {
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
            }
            
            if (aVal < bVal) return direction === 'asc' ? -1 : 1;
            if (aVal > bVal) return direction === 'asc' ? 1 : -1;
            return 0;
        });
    },

    /**
     * Add table sorting functionality
     */
    addSortingToTable(tableElement, data, renderCallback) {
        let currentSort = { key: null, direction: 'asc' };
        
        tableElement.addEventListener('click', (e) => {
            const th = e.target.closest('th[data-sort]');
            if (!th) return;
            
            const sortKey = th.dataset.sort;
            const direction = th.dataset.direction;
            
            // Update sort state
            currentSort = { key: sortKey, direction };
            
            // Sort data and re-render
            const sortedData = this.sortData(data, sortKey, direction);
            renderCallback(sortedData, currentSort);
            
            // Update header directions
            tableElement.querySelectorAll('th[data-sort]').forEach(header => {
                if (header === th) {
                    header.dataset.direction = direction === 'asc' ? 'desc' : 'asc';
                } else {
                    header.dataset.direction = 'asc';
                }
            });
        });
    }
};

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('File Categorizer Web Interface loaded');
    
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add global error handler
    window.addEventListener('error', function(e) {
        console.error('Global error:', e.error);
        Utils.showToast('An unexpected error occurred', 'danger');
    });
    
    // Add unhandled promise rejection handler
    window.addEventListener('unhandledrejection', function(e) {
        console.error('Unhandled promise rejection:', e.reason);
        Utils.showToast('An unexpected error occurred', 'danger');
    });
});

// Export for use in other scripts
window.App = App;
window.Utils = Utils;
window.API = API;
window.TableUtils = TableUtils;