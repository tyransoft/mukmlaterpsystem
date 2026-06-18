// ERP Main JavaScript - Vanilla JS

const ERP = {
  // CSRF Token
  getCSRF() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1].trim() : '';
  },

  // Show toast notification
  toast(message, type = 'success') {
    const existing = document.querySelector('.erp-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    toast.className = `erp-toast erp-toast-${type}`;
    toast.innerHTML = `<span>${icons[type] || '✅'}</span><span>${message}</span>`;
    toast.style.cssText = `
      position: fixed; bottom: 24px; left: 24px; z-index: 9999;
      background: ${type === 'success' ? '#276749' : type === 'error' ? '#c53030' : '#744210'};
      color: white; padding: 12px 20px; border-radius: 10px;
      font-family: Tajawal, sans-serif; font-size: 14px;
      display: flex; gap: 8px; align-items: center;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      animation: slideInUp 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.animation = 'fadeOut 0.3s ease'; setTimeout(() => toast.remove(), 300); }, 3000);
  },

  // AJAX fetch wrapper
  async fetch(url, options = {}) {
    const defaults = {
      headers: {
        'X-CSRFToken': this.getCSRF(),
        'Content-Type': 'application/json',
      }
    };
    const res = await fetch(url, { ...defaults, ...options });
    return res.json();
  },

  // Confirm delete
  async confirmDelete(url, name, callback) {
    if (!confirm(`هل أنت متأكد من حذف "${name}"؟`)) return;
    try {
      const data = await this.fetch(url, { method: 'POST' });
      if (data.success) {
        this.toast('تم الحذف بنجاح');
        if (callback) callback();
        else window.location.reload();
      } else {
        this.toast(data.error || 'حدث خطأ', 'error');
      }
    } catch (e) {
      this.toast('خطأ في الاتصال', 'error');
    }
  },

  // Format currency
  formatCurrency(amount) {
    return new Intl.NumberFormat('ar-SA', { style: 'currency', currency: 'SAR' }).format(amount);
  },

  // Auto-dismiss alerts
  initAlerts() {
    document.querySelectorAll('.alert[data-auto-dismiss]').forEach(alert => {
      setTimeout(() => { alert.style.animation = 'fadeOut 0.5s ease'; setTimeout(() => alert.remove(), 500); }, 4000);
    });
  }
};

// ============ INVOICE CREATE PAGE ============
const InvoiceManager = {
  items: [],
  counter: 0,

  init() {
    this.bindEvents();
    this.updateTotals();
  },

  bindEvents() {
    const addBtn = document.getElementById('add-item-btn');
    if (addBtn) addBtn.addEventListener('click', () => this.addItem());

    const productSearch = document.getElementById('product-search-input');
    if (productSearch) {
      let timer;
      productSearch.addEventListener('input', (e) => {
        clearTimeout(timer);
        timer = setTimeout(() => this.searchProducts(e.target.value), 300);
      });
    }

    const customerSearch = document.getElementById('customer-search-input');
    if (customerSearch) {
      let timer;
      customerSearch.addEventListener('input', (e) => {
        clearTimeout(timer);
        timer = setTimeout(() => this.searchCustomers(e.target.value), 300);
      });
    }

    const discountInput = document.getElementById('id_discount');
    if (discountInput) discountInput.addEventListener('input', () => this.updateTotals());
  },

  async searchProducts(query) {
    if (query.length < 2) return;
    const branchId = document.getElementById('id_branch')?.value || '';
    const res = await fetch(`/products/search/?q=${encodeURIComponent(query)}&branch_id=${branchId}`);
    const data = await res.json();
    this.showProductDropdown(data.products);
  },

  showProductDropdown(products) {
    let dropdown = document.getElementById('product-dropdown');
    if (!dropdown) {
      dropdown = document.createElement('div');
      dropdown.id = 'product-dropdown';
      dropdown.style.cssText = `
        position: absolute; background: white; border: 1.5px solid #E2E8F0;
        border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        z-index: 100; width: 320px; max-height: 300px; overflow-y: auto;
        font-family: Tajawal, sans-serif;
      `;
      document.getElementById('product-search-input').parentNode.style.position = 'relative';
      document.getElementById('product-search-input').after(dropdown);
    }
    if (!products.length) { dropdown.innerHTML = '<div style="padding:12px;color:#718096;font-size:13px;text-align:center;">لا توجد نتائج</div>'; return; }
    dropdown.innerHTML = products.map(p => `
      <div onclick="InvoiceManager.selectProduct(${JSON.stringify(p).replace(/"/g, '&quot;')})"
           style="padding:10px 14px;cursor:pointer;border-bottom:1px solid #f0f0f0;transition:background 0.1s;"
           onmouseover="this.style.background='#FFF5EE'" onmouseout="this.style.background='white'">
        <div style="font-weight:600;font-size:13px;">${p.name}</div>
        <div style="font-size:11px;color:#718096;">${p.code} | السعر: ${p.selling_price.toFixed(2)} | المخزون: ${p.stock}</div>
      </div>
    `).join('');
  },

  selectProduct(product) {
    document.getElementById('product-dropdown')?.remove();
    document.getElementById('product-search-input').value = '';
    this.addItemRow(product);
  },

  addItemRow(product) {
    this.counter++;
    const idx = this.counter;
    const tbody = document.getElementById('invoice-items-body');
    if (!tbody) return;
    const tr = document.createElement('tr');
    tr.id = `item-row-${idx}`;
    tr.innerHTML = `
      <td>
        <input type="hidden" name="product_id[]" value="${product.id}">
        ${product.name}
        <div style="font-size:11px;color:#718096;">${product.code}</div>
      </td>
      <td>
        <input type="number" name="quantity[]" value="1" min="1"
               class="form-control" style="width:80px;"
               onchange="InvoiceManager.updateRowTotal(${idx})"
               data-price="${product.selling_price}" data-loyalty="${product.loyalty_points}" id="qty-${idx}">
      </td>
      <td>
        <input type="number" name="unit_price[]" value="${product.selling_price}" step="0.01" min="0"
               class="form-control" style="width:100px;"
               onchange="InvoiceManager.updateRowTotal(${idx})" id="price-${idx}">
      </td>
      <td id="total-${idx}">${product.selling_price.toFixed(2)}</td>
      <td id="points-${idx}">${product.loyalty_points}</td>
      <td>
        <button type="button" class="btn btn-danger btn-icon btn-sm" onclick="InvoiceManager.removeRow(${idx})">✕</button>
      </td>
    `;
    tbody.appendChild(tr);
    this.updateTotals();
  },

  updateRowTotal(idx) {
    const qty = parseFloat(document.getElementById(`qty-${idx}`)?.value || 0);
    const price = parseFloat(document.getElementById(`price-${idx}`)?.value || 0);
    const loyalty = parseFloat(document.getElementById(`qty-${idx}`)?.dataset.loyalty || 0);
    const total = qty * price;
    const el = document.getElementById(`total-${idx}`);
    const pts = document.getElementById(`points-${idx}`);
    if (el) el.textContent = total.toFixed(2);
    if (pts) pts.textContent = (qty * loyalty).toFixed(0);
    this.updateTotals();
  },

  removeRow(idx) {
    document.getElementById(`item-row-${idx}`)?.remove();
    this.updateTotals();
  },

  updateTotals() {
    let subtotal = 0, totalPoints = 0;
    document.querySelectorAll('#invoice-items-body tr').forEach(row => {
      const idMatch = row.id.match(/item-row-(\d+)/);
      if (!idMatch) return;
      const idx = idMatch[1];
      const qty = parseFloat(document.getElementById(`qty-${idx}`)?.value || 0);
      const price = parseFloat(document.getElementById(`price-${idx}`)?.value || 0);
      const loyalty = parseFloat(document.getElementById(`qty-${idx}`)?.dataset.loyalty || 0);
      subtotal += qty * price;
      totalPoints += qty * loyalty;
    });
    const discount = parseFloat(document.getElementById('id_discount')?.value || 0);
    const total = subtotal - discount;
    const el = id => document.getElementById(id);
    if (el('subtotal-display')) el('subtotal-display').textContent = subtotal.toFixed(2);
    if (el('total-display')) el('total-display').textContent = total.toFixed(2);
    if (el('points-display')) el('points-display').textContent = totalPoints.toFixed(0);
    if (el('discount-display')) el('discount-display').textContent = discount.toFixed(2);
  },

  async searchCustomers(query) {
    if (query.length < 2) return;
    const res = await fetch(`/customers/search/?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    this.showCustomerDropdown(data.customers);
  },

  showCustomerDropdown(customers) {
    let dropdown = document.getElementById('customer-dropdown');
    if (!dropdown) {
      dropdown = document.createElement('div');
      dropdown.id = 'customer-dropdown';
      dropdown.style.cssText = `
        position: absolute; background: white; border: 1.5px solid #E2E8F0;
        border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.12);
        z-index: 100; width: 280px; max-height: 240px; overflow-y: auto;
        font-family: Tajawal, sans-serif;
      `;
      document.getElementById('customer-search-input').parentNode.style.position = 'relative';
      document.getElementById('customer-search-input').after(dropdown);
    }
    dropdown.innerHTML = customers.map(c => `
      <div onclick="InvoiceManager.selectCustomer(${c.id}, '${c.full_name}', '${c.phone}')"
           style="padding:10px 14px;cursor:pointer;border-bottom:1px solid #f0f0f0;"
           onmouseover="this.style.background='#FFF5EE'" onmouseout="this.style.background='white'">
        <div style="font-weight:600;font-size:13px;">${c.full_name}</div>
        <div style="font-size:11px;color:#718096;">${c.phone} | نقاط: ${c.loyalty_points}</div>
      </div>
    `).join('');
  },

  selectCustomer(id, name, phone) {
    document.getElementById('customer-dropdown')?.remove();
    document.getElementById('customer-search-input').value = name;
    const select = document.getElementById('id_customer');
    if (select) {
      let opt = select.querySelector(`option[value="${id}"]`);
      if (!opt) { opt = new Option(name, id); select.add(opt); }
      select.value = id;
    }
  }
};

function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='));
    return cookieValue ? cookieValue.split('=')[1] : '';
}


function showToast(message, type = 'success') {
    const colors = {
        success: '#22c55e',
        error: '#ef4444',
        warning: '#f59e0b',
        info: '#3b82f6'
    };
    
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        background: ${colors[type] || colors.success};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: fadeOut 2.5s ease-in-out forwards;
    `;
    toast.textContent = message;
    
    // إضافة animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeOut {
            0% { opacity: 1; }
            70% { opacity: 1; }
            100% { opacity: 0; display: none; }
        }
    `;
    document.head.appendChild(style);
    
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 500);
    }, 2500);
}

async function markTransferred(pk) {
    if (!confirm('هل تم تحويل نقاط الولاء هذه إلى النظام الخارجي؟')) return;
    
    try {
        const response = await fetch(`/loyalty/${pk}/mark-transferred/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'تم التحويل بنجاح');
            document.getElementById(`loyalty-row-${pk}`)?.remove();
        } else {
            showToast(data.error || 'حدث خطأ', 'error');
        }
    } catch (error) {
        showToast('حدث خطأ في الاتصال', 'error');
        console.error(error);
    }
}

async function markAllTransferred(customerId, branchId) {
    if (!confirm('هل تريد تحويل جميع النقاط المعلقة؟')) return;
    
    try {
        const fd = new FormData();
        if (customerId) fd.append('customer_id', customerId);
        if (branchId) fd.append('branch_id', branchId);
        
        const response = await fetch('/loyalty/mark-all/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
            },
            body: fd,
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message);
            setTimeout(() => location.reload(), 1200);
        } else {
            showToast(data.error || 'حدث خطأ', 'error');
        }
    } catch (error) {
        showToast('حدث خطأ في الاتصال', 'error');
        console.error(error);
    }
}
// ============ CONFIRM INVOICE ============
async function confirmInvoice(pk) {
  if (!confirm('هل تريد تأكيد هذه الفاتورة وتحديث المخزون؟')) return;
  const data = await ERP.fetch(`/invoices/${pk}/confirm/`, { method: 'POST' });
  if (data.success) { ERP.toast('تم تأكيد الفاتورة بنجاح'); setTimeout(() => location.reload(), 1200); }
  else ERP.toast(data.error, 'error');
}

async function cancelInvoice(pk) {
  if (!confirm('هل تريد إلغاء هذه الفاتورة؟')) return;
  const data = await ERP.fetch(`/invoices/${pk}/cancel/`, { method: 'POST' });
  if (data.success) { ERP.toast('تم إلغاء الفاتورة'); setTimeout(() => location.reload(), 1200); }
  else ERP.toast(data.error, 'error');
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideInUp { from { transform: translateY(30px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
  @keyframes fadeOut { to { opacity: 0; transform: translateY(10px); } }
`;
document.head.appendChild(style);

// Init
document.addEventListener('DOMContentLoaded', () => {
  ERP.initAlerts();
  if (document.getElementById('invoice-items-body')) InvoiceManager.init();
  // Close dropdowns on outside click
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#product-search-input')) document.getElementById('product-dropdown')?.remove();
    if (!e.target.closest('#customer-search-input')) document.getElementById('customer-dropdown')?.remove();
  });
});
