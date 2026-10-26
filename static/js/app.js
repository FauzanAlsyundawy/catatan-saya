/**
 * Catatan Saya - Client Application Logic
 * Minimal, zero external dependencies, robust CSRF & UX handling.
 */

document.addEventListener('DOMContentLoaded', () => {
    initPasswordToggle();
    initMobileDrawer();
    initDeleteModal();
    initAutoDismissAlerts();
});

/* Toast Notification Utility */
function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Inline SVG icon
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else if (type === 'error') {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#e11d48" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `
        <div style="flex-shrink:0;">${iconSvg}</div>
        <div style="flex:1;">${escapeHtml(message)}</div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 200ms ease';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        }[m];
    });
}

/* Password Visibility Toggle */
function initPasswordToggle() {
    const toggleBtns = document.querySelectorAll('.password-toggle-btn');
    toggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target') || 'password';
            const input = document.getElementById(targetId);
            if (!input) return;

            const isPassword = input.type === 'password';
            input.type = isPassword ? 'text' : 'password';

            // Toggle SVG icon
            if (isPassword) {
                // Eye Off icon
                btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"></path><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"></path><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"></path><line x1="2" y1="2" x2="22" y2="22"></line></svg>`;
                btn.setAttribute('aria-label', 'Sembunyikan password');
            } else {
                // Eye icon
                btn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
                btn.setAttribute('aria-label', 'Tampilkan password');
            }
        });
    });
}

/* Mobile Drawer (Sidebar) */
function initMobileDrawer() {
    const toggleBtn = document.getElementById('mobile-drawer-btn');
    const sidebar = document.getElementById('app-sidebar');
    if (!toggleBtn || !sidebar) return;

    // Create backdrop for mobile drawer
    let backdrop = document.getElementById('drawer-backdrop');
    if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.id = 'drawer-backdrop';
        backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:35;display:none;';
        document.body.appendChild(backdrop);
    }

    const openDrawer = () => {
        sidebar.classList.add('open');
        backdrop.style.display = 'block';
    };

    const closeDrawer = () => {
        sidebar.classList.remove('open');
        backdrop.style.display = 'none';
    };

    toggleBtn.addEventListener('click', () => {
        if (sidebar.classList.contains('open')) {
            closeDrawer();
        } else {
            openDrawer();
        }
    });

    backdrop.addEventListener('click', closeDrawer);
}

/* Delete File Confirmation Modal */
function initDeleteModal() {
    const modalBackdrop = document.getElementById('delete-modal');
    if (!modalBackdrop) return;

    const modalFilename = document.getElementById('modal-delete-filename');
    const cancelBtn = document.getElementById('modal-btn-cancel');
    const confirmBtn = document.getElementById('modal-btn-confirm');

    let currentFileId = null;
    let currentCategorySlug = null;

    // Open modal event
    document.querySelectorAll('.btn-delete-file').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            currentFileId = btn.getAttribute('data-id');
            currentCategorySlug = btn.getAttribute('data-category');
            const fileName = btn.getAttribute('data-filename');

            if (modalFilename) modalFilename.textContent = fileName;
            modalBackdrop.classList.add('active');
        });
    });

    const closeModal = () => {
        modalBackdrop.classList.remove('active');
        currentFileId = null;
    };

    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop) closeModal();
    });

    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            if (!currentFileId) return;

            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Menghapus...';

            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

            try {
                const response = await fetch(`/api/files/${currentFileId}`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRF-Token': csrfToken,
                        'Accept': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok && data.success) {
                    showToast(data.message || 'File berhasil dihapus', 'success');
                    closeModal();
                    // Remove row from table or reload
                    const row = document.getElementById(`file-row-${currentFileId}`);
                    if (row) {
                        row.remove();
                        // Check if table empty
                        const remaining = document.querySelectorAll('.file-row-item');
                        if (remaining.length === 0) {
                            setTimeout(() => window.location.reload(), 500);
                        }
                    } else {
                        setTimeout(() => window.location.reload(), 500);
                    }
                } else {
                    showToast(data.detail || 'Gagal menghapus file', 'error');
                }
            } catch (err) {
                showToast('Kesalahan jaringan saat menghapus file', 'error');
            } finally {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Hapus File';
            }
        });
    }
}

/* Auto dismiss flash messages */
function initAutoDismissAlerts() {
    const flash = document.querySelectorAll('.alert-flash');
    flash.forEach(el => {
        setTimeout(() => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 300ms ease';
            setTimeout(() => el.remove(), 350);
        }, 5000);
    });
}
