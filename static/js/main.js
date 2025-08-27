/**
 * AgencySales Pro - Main JavaScript File
 * Provides common functionality across the application
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // Initialize Bootstrap components
    initializeBootstrapComponents();
    
    // Setup form validations
    setupFormValidation();
    
    // Setup confirmation dialogs
    setupConfirmationDialogs();
    
    // Setup dynamic form behaviors
    setupDynamicForms();
    
    // Setup utility functions
    setupUtilities();
    
    // Setup order form enhancements
    setupOrderFormEnhancements();
    
    // Setup table enhancements
    setupTableEnhancements();
    
    // Setup notification handling
    setupNotifications();
    
    console.log('AgencySales Pro JavaScript initialized');
});

/**
 * Initialize Bootstrap components
 */
function initializeBootstrapComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Initialize modals
    const modalElements = document.querySelectorAll('.modal');
    modalElements.forEach(function(modalEl) {
        new bootstrap.Modal(modalEl);
    });
}

/**
 * Setup form validation
 */
function setupFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Focus on first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                }
            }
            
            form.classList.add('was-validated');
        }, false);
    });
    
    // Real-time validation for specific fields
    setupRealTimeValidation();
}

/**
 * Setup real-time validation
 */
function setupRealTimeValidation() {
    // Email validation
    const emailInputs = document.querySelectorAll('input[type="email"]');
    emailInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            validateEmail(input);
        });
    });
    
    // Password confirmation
    const passwordConfirmInputs = document.querySelectorAll('input[name="confirm_password"]');
    passwordConfirmInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            const password = document.querySelector('input[name="password"]');
            if (password) {
                validatePasswordMatch(password, input);
            }
        });
    });
    
    // SKU uniqueness (basic client-side check)
    const skuInputs = document.querySelectorAll('input[name="sku"]');
    skuInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            validateSKUFormat(input);
        });
    });
}

/**
 * Validate email format
 */
function validateEmail(input) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const isValid = emailRegex.test(input.value);
    
    if (input.value && !isValid) {
        input.setCustomValidity('Please enter a valid email address');
        input.classList.add('is-invalid');
    } else {
        input.setCustomValidity('');
        input.classList.remove('is-invalid');
    }
}

/**
 * Validate password match
 */
function validatePasswordMatch(passwordInput, confirmInput) {
    if (passwordInput.value !== confirmInput.value) {
        confirmInput.setCustomValidity('Passwords do not match');
        confirmInput.classList.add('is-invalid');
    } else {
        confirmInput.setCustomValidity('');
        confirmInput.classList.remove('is-invalid');
    }
}

/**
 * Validate SKU format
 */
function validateSKUFormat(input) {
    const skuRegex = /^[A-Z0-9-]{3,20}$/;
    const isValid = skuRegex.test(input.value);
    
    if (input.value && !isValid) {
        input.setCustomValidity('SKU should be 3-20 characters, uppercase letters, numbers, and hyphens only');
        input.classList.add('is-invalid');
    } else {
        input.setCustomValidity('');
        input.classList.remove('is-invalid');
    }
}

/**
 * Setup confirmation dialogs
 */
function setupConfirmationDialogs() {
    // Delete confirmations
    const deleteButtons = document.querySelectorAll('[onclick*="confirm"]');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            const message = button.getAttribute('onclick').match(/'([^']+)'/);
            if (message && !confirm(message[1])) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Status change confirmations
    const statusButtons = document.querySelectorAll('button[title*="activate"], button[title*="Activate"], button[title*="deactivate"], button[title*="Deactivate"]');
    statusButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            const action = button.getAttribute('title').toLowerCase();
            if (!confirm(`Are you sure you want to ${action} this item?`)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Setup dynamic form behaviors
 */
function setupDynamicForms() {
    // Auto-format phone numbers
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            formatPhoneNumber(input);
        });
    });
    
    // Auto-uppercase SKU inputs
    const skuInputs = document.querySelectorAll('input[name="sku"]');
    skuInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            input.value = input.value.toUpperCase();
        });
    });
    
    // Auto-format currency inputs
    const currencyInputs = document.querySelectorAll('input[step="0.01"]');
    currencyInputs.forEach(function(input) {
        input.addEventListener('blur', function() {
            formatCurrency(input);
        });
    });
}

/**
 * Format phone number
 */
function formatPhoneNumber(input) {
    let value = input.value.replace(/\D/g, '');
    if (value.length >= 6) {
        value = value.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
    } else if (value.length >= 3) {
        value = value.replace(/(\d{3})(\d{0,3})/, '($1) $2');
    }
    input.value = value;
}

/**
 * Format currency input
 */
function formatCurrency(input) {
    if (input.value) {
        const value = parseFloat(input.value);
        if (!isNaN(value)) {
            input.value = value.toFixed(2);
        }
    }
}

/**
 * Setup utility functions
 */
function setupUtilities() {
    // Copy to clipboard functionality
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            showNotification('Copied to clipboard!', 'success');
        }).catch(function() {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            showNotification('Copied to clipboard!', 'success');
        });
    };
    
    // Format number with commas
    window.formatNumber = function(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    };
    
    // Format currency
    window.formatCurrency = function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    };
    
    // Debounce function
    window.debounce = function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    };
}

/**
 * Setup order form enhancements
 */
function setupOrderFormEnhancements() {
    const orderForm = document.getElementById('orderForm');
    if (!orderForm) return;
    
    // Already implemented in the template, but adding additional enhancements
    setupProductSearch();
    setupOrderCalculations();
    setupOrderValidation();
}

/**
 * Setup product search functionality
 */
function setupProductSearch() {
    const productSelects = document.querySelectorAll('select[name="products"]');
    productSelects.forEach(function(select) {
        // Add search functionality to product selects
        select.addEventListener('change', function() {
            const selectedOption = select.options[select.selectedIndex];
            if (selectedOption && selectedOption.dataset.price) {
                const quantityInput = select.closest('.order-item').querySelector('input[name="quantities"]');
                if (quantityInput && !quantityInput.value) {
                    quantityInput.value = 1;
                    quantityInput.focus();
                }
            }
        });
    });
}

/**
 * Setup order calculations
 */
function setupOrderCalculations() {
    const orderForm = document.getElementById('orderForm');
    if (!orderForm) return;
    
    // Enhanced calculation with real-time updates
    const calculateTotal = window.debounce(function() {
        let subtotal = 0;
        const items = orderForm.querySelectorAll('.order-item');
        
        items.forEach(function(item) {
            const select = item.querySelector('select[name="products"]');
            const quantityInput = item.querySelector('input[name="quantities"]');
            
            if (select && select.value && quantityInput && quantityInput.value) {
                const price = parseFloat(select.options[select.selectedIndex].dataset.price || 0);
                const quantity = parseInt(quantityInput.value || 0);
                subtotal += price * quantity;
            }
        });
        
        const discount = parseFloat(document.getElementById('discount')?.value || 0);
        const tax = parseFloat(document.getElementById('tax')?.value || 0);
        
        const total = Math.max(0, subtotal - discount + tax);
        const totalElement = document.getElementById('totalAmount');
        
        if (totalElement) {
            totalElement.textContent = window.formatCurrency(total);
            totalElement.classList.add('fade-in');
        }
        
        // Update subtotal display if exists
        const subtotalElement = document.getElementById('subtotalAmount');
        if (subtotalElement) {
            subtotalElement.textContent = window.formatCurrency(subtotal);
        }
    }, 300);
    
    // Attach event listeners
    orderForm.addEventListener('change', calculateTotal);
    orderForm.addEventListener('input', calculateTotal);
}

/**
 * Setup order validation
 */
function setupOrderValidation() {
    const orderForm = document.getElementById('orderForm');
    if (!orderForm) return;
    
    orderForm.addEventListener('submit', function(e) {
        let hasValidItems = false;
        const items = orderForm.querySelectorAll('.order-item');
        
        items.forEach(function(item) {
            const select = item.querySelector('select[name="products"]');
            const quantityInput = item.querySelector('input[name="quantities"]');
            
            if (select && select.value && quantityInput && quantityInput.value > 0) {
                hasValidItems = true;
            }
        });
        
        if (!hasValidItems) {
            e.preventDefault();
            showNotification('Please add at least one product to the order', 'warning');
            return false;
        }
        
        // Show loading state
        const submitButton = orderForm.querySelector('button[type="submit"]');
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Creating Order...';
        }
    });
}

/**
 * Setup table enhancements
 */
function setupTableEnhancements() {
    // Add sorting functionality to tables
    const sortableTables = document.querySelectorAll('.table-sortable');
    sortableTables.forEach(function(table) {
        setupTableSorting(table);
    });
    
    // Add search functionality
    setupTableSearch();
    
    // Add row selection functionality
    setupRowSelection();
}

/**
 * Setup table sorting
 */
function setupTableSorting(table) {
    const headers = table.querySelectorAll('th[data-sort]');
    headers.forEach(function(header) {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            const column = header.dataset.sort;
            const currentSort = header.dataset.sortDirection || 'asc';
            const newSort = currentSort === 'asc' ? 'desc' : 'asc';
            
            // Remove sort indicators from other headers
            headers.forEach(function(h) {
                h.classList.remove('sort-asc', 'sort-desc');
                delete h.dataset.sortDirection;
            });
            
            // Add sort indicator to current header
            header.classList.add(`sort-${newSort}`);
            header.dataset.sortDirection = newSort;
            
            sortTable(table, column, newSort);
        });
    });
}

/**
 * Sort table by column
 */
function sortTable(table, column, direction) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort(function(a, b) {
        const aValue = a.querySelector(`td[data-${column}]`)?.textContent || a.cells[getColumnIndex(table, column)]?.textContent || '';
        const bValue = b.querySelector(`td[data-${column}]`)?.textContent || b.cells[getColumnIndex(table, column)]?.textContent || '';
        
        // Try to parse as numbers
        const aNum = parseFloat(aValue.replace(/[^0-9.-]/g, ''));
        const bNum = parseFloat(bValue.replace(/[^0-9.-]/g, ''));
        
        if (!isNaN(aNum) && !isNaN(bNum)) {
            return direction === 'asc' ? aNum - bNum : bNum - aNum;
        }
        
        // Sort as strings
        return direction === 'asc' 
            ? aValue.localeCompare(bValue)
            : bValue.localeCompare(aValue);
    });
    
    // Reorder DOM elements
    rows.forEach(function(row) {
        tbody.appendChild(row);
    });
}

/**
 * Get column index by data attribute
 */
function getColumnIndex(table, column) {
    const headers = table.querySelectorAll('th');
    for (let i = 0; i < headers.length; i++) {
        if (headers[i].dataset.sort === column) {
            return i;
        }
    }
    return 0;
}

/**
 * Setup table search functionality
 */
function setupTableSearch() {
    const searchInputs = document.querySelectorAll('.table-search');
    searchInputs.forEach(function(input) {
        const targetTable = document.querySelector(input.dataset.target);
        if (targetTable) {
            input.addEventListener('input', window.debounce(function() {
                filterTable(targetTable, input.value);
            }, 300));
        }
    });
}

/**
 * Filter table rows based on search term
 */
function filterTable(table, searchTerm) {
    const rows = table.querySelectorAll('tbody tr');
    const term = searchTerm.toLowerCase();
    
    rows.forEach(function(row) {
        const text = row.textContent.toLowerCase();
        const shouldShow = !term || text.includes(term);
        row.style.display = shouldShow ? '' : 'none';
    });
    
    // Show no results message if needed
    const visibleRows = table.querySelectorAll('tbody tr:not([style*="display: none"])');
    const noResultsRow = table.querySelector('.no-results');
    
    if (visibleRows.length === 0 && term && !noResultsRow) {
        const tbody = table.querySelector('tbody');
        const colCount = table.querySelectorAll('thead th').length;
        const noResultsRow = document.createElement('tr');
        noResultsRow.className = 'no-results';
        noResultsRow.innerHTML = `<td colspan="${colCount}" class="text-center text-muted py-4">No results found for "${searchTerm}"</td>`;
        tbody.appendChild(noResultsRow);
    } else if (visibleRows.length > 0 && noResultsRow) {
        noResultsRow.remove();
    }
}

/**
 * Setup row selection
 */
function setupRowSelection() {
    const selectAllCheckboxes = document.querySelectorAll('.select-all');
    selectAllCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            const table = checkbox.closest('table');
            const rowCheckboxes = table.querySelectorAll('tbody input[type="checkbox"]');
            rowCheckboxes.forEach(function(rowCheckbox) {
                rowCheckbox.checked = checkbox.checked;
            });
            updateBulkActions(table);
        });
    });
    
    // Individual row selection
    const tables = document.querySelectorAll('table');
    tables.forEach(function(table) {
        const rowCheckboxes = table.querySelectorAll('tbody input[type="checkbox"]');
        rowCheckboxes.forEach(function(checkbox) {
            checkbox.addEventListener('change', function() {
                updateSelectAll(table);
                updateBulkActions(table);
            });
        });
    });
}

/**
 * Update select all checkbox state
 */
function updateSelectAll(table) {
    const selectAllCheckbox = table.querySelector('.select-all');
    const rowCheckboxes = table.querySelectorAll('tbody input[type="checkbox"]');
    const checkedBoxes = table.querySelectorAll('tbody input[type="checkbox"]:checked');
    
    if (selectAllCheckbox) {
        if (checkedBoxes.length === 0) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = false;
        } else if (checkedBoxes.length === rowCheckboxes.length) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = true;
        } else {
            selectAllCheckbox.indeterminate = true;
            selectAllCheckbox.checked = false;
        }
    }
}

/**
 * Update bulk actions based on selection
 */
function updateBulkActions(table) {
    const checkedBoxes = table.querySelectorAll('tbody input[type="checkbox"]:checked');
    const bulkActions = document.querySelectorAll('.bulk-actions');
    
    bulkActions.forEach(function(actions) {
        if (checkedBoxes.length > 0) {
            actions.style.display = 'block';
            actions.classList.add('slide-up');
        } else {
            actions.style.display = 'none';
        }
    });
}

/**
 * Setup notification handling
 */
function setupNotifications() {
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
    
    // Global notification function
    window.showNotification = function(message, type = 'info', duration = 5000) {
        const alertContainer = document.getElementById('alert-container') || createAlertContainer();
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        alertContainer.appendChild(alertDiv);
        
        // Auto-dismiss
        if (duration > 0) {
            setTimeout(function() {
                const bsAlert = new bootstrap.Alert(alertDiv);
                bsAlert.close();
            }, duration);
        }
        
        return alertDiv;
    };
}

/**
 * Create alert container if it doesn't exist
 */
function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alert-container';
    container.style.position = 'fixed';
    container.style.top = '20px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.maxWidth = '400px';
    
    document.body.appendChild(container);
    return container;
}

/**
 * Global error handler
 */
window.addEventListener('error', function(e) {
    console.error('JavaScript Error:', e.error);
    showNotification('An unexpected error occurred. Please refresh the page.', 'error');
});

/**
 * Handle unhandled promise rejections
 */
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled Promise Rejection:', e.reason);
    showNotification('An error occurred while processing your request.', 'error');
});

/**
 * Utility function to format dates
 */
window.formatDate = function(dateString, options = {}) {
    const date = new Date(dateString);
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    };
    
    return date.toLocaleDateString('en-US', { ...defaultOptions, ...options });
};

/**
 * Utility function to format date and time
 */
window.formatDateTime = function(dateString) {
    return window.formatDate(dateString, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

// Export functions for potential module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        showNotification: window.showNotification,
        formatCurrency: window.formatCurrency,
        formatNumber: window.formatNumber,
        formatDate: window.formatDate,
        formatDateTime: window.formatDateTime,
        debounce: window.debounce,
        copyToClipboard: window.copyToClipboard
    };
}
