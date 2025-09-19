/**
 * AgencySales Pro - Order Form V2
 * Handles dynamic interactions for the new order creation form.
 */
const OrderForm = (function() {
    // State
    let state = {
        customer: null,
        items: [],
        taxCodes: {},
        customerSelect: null,
        productSelect: null
    };

    // DOM Elements
    const DOMElements = {
        customerSelect: '#customer-select',
        productSelect: '#product-select',
        inline: {
            qty: '#inline-qty',
            price: '#inline-price',
            discount: '#inline-discount',
            total: '#inline-total',
            addBtn: '#inline-add-btn',
        },
        orderItemsBody: '#order-items-body',
        noItemsRow: '#no-items-row',
        itemRowTemplate: '#item-row-template',
        summary: {
            grandTotal: '#summary-grand-total',
        },
        saveOrderBtn: '#save-order-btn',
        orderSubtotal: '#order-subtotal',
        orderTax: '#order-tax',
        orderDiscount: '#order-discount',
        deliveryDate: '#delivery-date',
        orderNotes: '#order-notes',
    };
    // Private Methods
    function bindEvents() {
        document.querySelector(DOMElements.inline.addBtn).addEventListener('click', addInlineItemToCart);
        
        // Add keydown listener for inline inputs to facilitate quick entry
        const inlineEnterInputs = [DOMElements.inline.qty, DOMElements.inline.price, DOMElements.inline.discount];
        inlineEnterInputs.forEach(selector => {
            document.querySelector(selector).addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    addInlineItemToCart();
                }
            });
        });

        // Add input listeners for real-time inline total calculation
        const inlineCalcInputs = [DOMElements.inline.qty, DOMElements.inline.price, DOMElements.inline.discount];
        inlineCalcInputs.forEach(selector => {
            document.querySelector(selector).addEventListener('input', calculateInlineTotal);
        });

        document.querySelector(DOMElements.orderItemsBody).addEventListener('change', handleItemChange);
        document.querySelector(DOMElements.orderItemsBody).addEventListener('click', handleItemClick);
        
        // Use the overridden save function if it exists, otherwise use the default
        document.querySelector(DOMElements.saveOrderBtn).addEventListener('click', saveOrder);

        document.querySelector(DOMElements.orderTax).addEventListener('input', calculateTotals);
        document.querySelector(DOMElements.orderDiscount).addEventListener('input', calculateTotals);
    }

    function fetchTaxCodes() {
        fetch('/order/api/tax-codes')
            .then(res => res.json())
            .then(data => {
                state.taxCodes = data;
            });
    }

    function populateTaxDropdown(selectElement, selectedValue) {
        selectElement.innerHTML = '';
        for (const code in state.taxCodes) {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = code;
            option.selected = (code === selectedValue);
            selectElement.appendChild(option);
        }
    }

    function setCustomer(customer) {
        // In edit mode, customer is fixed. In create mode, we set it.
        if (state.isEditMode) {
            state.customer = { id: document.getElementById('customer-id').value };
        } else {
            state.customer = customer;
        }
        // The UI panel is gone, but we still need to set the customer in the state.
        // state.customerSelect.disable(); // Keep the customer field enabled for easy changes.
        state.productSelect.focus();
    }

    function resetCustomer() {
        state.customer = null;
        if (state.customerSelect) {
            state.customerSelect.clear();
            state.customerSelect.enable();
        }
    }

    function selectProduct(product) {
        document.querySelector(DOMElements.inline.qty).value = 1;
        document.querySelector(DOMElements.inline.price).value = product.price.toFixed(2);
        document.querySelector(DOMElements.inline.discount).value = 0;
        document.querySelector(DOMElements.inline.qty).focus();
        document.querySelector(DOMElements.inline.qty).select();
        calculateInlineTotal(); // Calculate total for the selected product
    }

    function addInlineItemToCart() {
        const productId = state.productSelect.getValue();
        if (!productId) {
            showNotification('Please select a product first.', 'warning');
            return;
        }
        const product = state.productSelect.options[productId];
        const qty = parseFloat(document.querySelector(DOMElements.inline.qty).value);

        const existingItem = state.items.find(item => item.id === product.id);
        if (existingItem) {
            existingItem.quantity += qty;
        } else {
            state.items.push({
                ...product,
                quantity: qty,
                discount: parseFloat(document.querySelector(DOMElements.inline.discount).value),
            });
        }
        
        renderItems();
        resetInlineForm();
    }

    function resetInlineForm() {
        state.productSelect.clear();
        state.productSelect.focus();
        document.querySelector(DOMElements.inline.qty).value = 1;
        document.querySelector(DOMElements.inline.price).value = '';
        document.querySelector(DOMElements.inline.discount).value = 0;
        calculateInlineTotal(); // Reset inline total to zero
    }

    function renderItems() {
        const body = document.querySelector(DOMElements.orderItemsBody);
        const noItemsRow = document.querySelector(DOMElements.noItemsRow);
        body.innerHTML = '';

        if (state.items.length === 0) {
            if (noItemsRow) body.appendChild(noItemsRow);
            if (noItemsRow) noItemsRow.style.display = 'table-row';
        } else {
            if (noItemsRow) noItemsRow.style.display = 'none';
            state.items.forEach((item, index) => {
                const template = document.querySelector(DOMElements.itemRowTemplate).content.cloneNode(true);
                const row = template.querySelector('tr');
                row.dataset.itemId = item.id;

                row.querySelector('.item-name').textContent = item.name;
                row.querySelector('.item-sku').textContent = item.sku;
                const qtyInput = row.querySelector('.item-qty');
                qtyInput.value = item.quantity;
                row.querySelector('.item-price').value = item.price; // Hidden input
                row.querySelector('.item-discount').value = item.discount; // Hidden input
                body.appendChild(row);
            });
        }
        calculateTotals();
    }

    function calculateInlineTotal() {
        const price = parseFloat(document.querySelector(DOMElements.inline.price).value) || 0;
        const qty = parseFloat(document.querySelector(DOMElements.inline.qty).value) || 0;
        const discount = parseFloat(document.querySelector(DOMElements.inline.discount).value) || 0;

        const discountedPrice = price * (1 - (discount / 100));
        const lineTotal = discountedPrice * qty;

        const totalEl = document.querySelector(DOMElements.inline.total);
        totalEl.textContent = `₹${lineTotal.toFixed(2)}`;
    }

    function calculateTotals() {
        let subtotal = 0;

        state.items.forEach(item => {
            const discountedPrice = item.price * (1 - (item.discount / 100));
            const lineTotal = discountedPrice * item.quantity;

            // Update the row display
            const row = document.querySelector(`tr[data-item-id='${item.id}']`);
            if (row) {
                // Update the single line total display
                row.querySelector('.item-line-total').textContent = `₹${lineTotal.toFixed(2)}`;
            }
            
            subtotal += lineTotal;
        });

        // The desktop summary is removed, so these lines are no longer needed.
        // document.querySelector(DOMElements.summary.totalItems).textContent = totalItems;
        // document.querySelector(DOMElements.summary.subtotal).textContent = `₹${subtotal.toFixed(2)}`;
        const tax = parseFloat(document.querySelector(DOMElements.orderTax).value) || 0;
        const discount = parseFloat(document.querySelector(DOMElements.orderDiscount).value) || 0;
        const grandTotal = subtotal + tax - discount;

        document.querySelector(DOMElements.orderSubtotal).value = `₹${subtotal.toFixed(2)}`;
        document.querySelector(DOMElements.summary.grandTotal).textContent = `₹${grandTotal.toFixed(2)}`;
    }

    function handleItemChange(e) {
        const target = e.target;
        const row = target.closest('tr');
        if (!row || !row.dataset.itemId) return;

        const itemId = parseInt(row.dataset.itemId);
        const item = state.items.find(i => i.id === itemId);
        if (!item) return;

        if (target.classList.contains('item-qty')) item.quantity = parseFloat(target.value);
        // Price and discount are now hidden inputs, but logic remains the same if they were visible
        // if (target.classList.contains('item-price')) item.price = parseFloat(target.value);
        // if (target.classList.contains('item-discount')) item.discount = parseFloat(target.value);

        calculateTotals();
    }

    function handleItemClick(e) {
        const removeBtn = e.target.closest('.remove-item-btn');
        const qtyBtn = e.target.closest('.btn-qty');

        if (removeBtn) {
            const row = e.target.closest('tr');
            const itemId = parseInt(row.dataset.itemId);
            state.items = state.items.filter(i => i.id !== itemId);
            renderItems();
        } else if (qtyBtn) {
            const row = qtyBtn.closest('tr');
            const qtyInput = row.querySelector('.item-qty');
            let currentValue = parseFloat(qtyInput.value);
            const step = parseFloat(qtyInput.step) || 1;

            if (qtyBtn.dataset.action === 'increment') {
                currentValue += step;
            } else {
                currentValue = Math.max(step, currentValue - step); // Prevent going below min
            }
            qtyInput.value = currentValue.toFixed(2).replace('.00', '');

            // Manually trigger change event to recalculate totals
            qtyInput.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    async function saveOrder() {
        // In edit mode, the customer is pre-filled and read-only.
        const customerId = state.isEditMode 
            ? document.getElementById('customer-id').value 
            : (state.customer ? state.customer.id : null);

        if (!customerId) {
            return showNotification('Please select a customer.', 'error');
        }
        if (state.items.length === 0) {
            return showNotification('Please add at least one item to the order.', 'error');
        }

        const payload = {
            customer_id: customerId,
            delivery_date: document.querySelector(DOMElements.deliveryDate).value,
            notes: document.querySelector(DOMElements.orderNotes).value,
            tax: parseFloat(document.querySelector(DOMElements.orderTax).value) || 0,
            discount: parseFloat(document.querySelector(DOMElements.orderDiscount).value) || 0,
            items: state.items,
        };

        const btn = document.querySelector(DOMElements.saveOrderBtn);
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Saving...';

        try {
            const response = await fetch('/order/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();

            if (result.success) {
                window.location.href = result.redirect_url;
            } else {
                showNotification(result.error || 'Failed to save order.', 'error');
            }
        } catch (error) {
            showNotification('An unexpected error occurred.', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save me-2"></i>Save Order';
        }
    }

    // Public Methods
    return {
        init: function(config) {
            state.customerSelect = config.customerSelectInstance || null;
            state.productSelect = config.productSelectInstance;
            state.isEditMode = config.isEditMode || false;
            if (config.initialItems) {
                state.items = config.initialItems;
            }
            // fetchTaxCodes is not needed as per-item tax is removed
            fetchTaxCodes();
            bindEvents();
            renderItems(); // Initial render
        },
        getState: () => state, // Expose state for edit page
        resetCustomer: resetCustomer,
        setCustomer: setCustomer,
        selectProduct: selectProduct,
        // Expose saveOrder so it can be overridden
        saveOrder: saveOrder
    };
})();