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
            const targetId = btn.dataset.target || 'password';
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

    // Open modal event
    document.querySelectorAll('.btn-delete-file').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            currentFileId = btn.dataset.id;
            const fileName = btn.dataset.filename;

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
                console.error('Delete file error:', err);
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


/* ==========================================================================
   V2.0 ENTERPRISE UPGRADE ENHANCEMENTS
   ========================================================================== */

/* 1. Global Search (Real-time with Debounce & Ctrl+K) */
function initGlobalSearch() {
    const searchBar = document.getElementById('global-search-bar');
    const searchInput = document.getElementById('global-search-input');
    const dropdown = document.getElementById('search-dropdown');
    if (!searchBar || !searchInput || !dropdown) return;

    let debounceTimer = null;

    // Ctrl+K / Cmd+K shortcut
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
        if (e.key === 'Escape' && document.activeElement === searchInput) {
            searchInput.blur();
            dropdown.classList.remove('active');
            dropdown.innerHTML = '';
        }
    });

    searchBar.addEventListener('click', () => searchInput.focus());

    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = searchInput.value.trim();
        if (q.length < 2) {
            dropdown.classList.remove('active');
            dropdown.innerHTML = '';
            return;
        }
        debounceTimer = setTimeout(() => performSearch(q), 280);
    });

    document.addEventListener('click', (e) => {
        if (!searchBar.closest('.global-search-wrapper')?.contains(e.target)) {
            dropdown.classList.remove('active');
        }
    });
}

async function performSearch(q) {
    const dropdown = document.getElementById('search-dropdown');
    if (!dropdown) return;
    dropdown.innerHTML = '<div class="search-no-result">Mencari...</div>';
    dropdown.classList.add('active');

    try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`, {
            headers: { 'Accept': 'application/json' }
        });
        if (!res.ok) {
            dropdown.innerHTML = '<div class="search-no-result">Sesi tidak valid, silakan muat ulang halaman.</div>';
            return;
        }
        const data = await res.json();
        if (!data.results || data.results.length === 0) {
            dropdown.innerHTML = `<div class="search-no-result">Tidak ada berkas yang cocok dengan "<strong>${escapeHtml(q)}</strong>"</div>`;
            return;
        }
        dropdown.innerHTML = data.results.map(r => `
            <a href="/api/files/download/${r.id}" class="search-result-item" title="Unduh ${escapeHtml(r.original_filename)}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/></svg>
                <div style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    <div style="font-weight:500;">${escapeHtml(r.original_filename)}</div>
                    <div style="font-size:11px; color:var(--text-muted);">${escapeHtml(r.size_formatted)}</div>
                </div>
                <span class="search-result-cat">${escapeHtml(r.category_slug)}</span>
            </a>
        `).join('');
    } catch (err) {
        console.error('Search fetch error:', err);
        dropdown.innerHTML = '<div class="search-no-result">Gagal terhubung ke server pencarian.</div>';
    }
}

/* 2. User Profile Dropdown */
function initUserProfileDropdown() {
    const btn = document.getElementById('user-profile-btn');
    const menu = document.getElementById('user-dropdown-menu');
    if (!btn || !menu) return;

    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        menu.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
        if (!btn.contains(e.target) && !menu.contains(e.target)) {
            menu.classList.remove('open');
        }
    });
}

/* 3. Sidebar Storage Progress Widget */
async function initStorageWidget() {
    const bar = document.getElementById('storage-progress-bar');
    const text = document.getElementById('storage-used-text');
    if (!bar || !text) return;

    try {
        const res = await fetch('/api/storage-info', { headers: { 'Accept': 'application/json' } });
        if (!res.ok) return;
        const data = await res.json();
        const CAP_BYTES = 7 * 1024 * 1024 * 1024; // 7 GB cap
        const totalBytes = data.total_bytes || 0;
        const pct = Math.min((totalBytes / CAP_BYTES) * 100, 100).toFixed(1);

        text.textContent = `${data.total_formatted || '0 B'} / 7 GB`;
        bar.style.width = `${Math.max(pct, totalBytes > 0 ? 2 : 0)}%`;

        if (pct > 85) {
            bar.style.backgroundColor = 'var(--status-danger)';
        } else if (pct > 65) {
            bar.style.backgroundColor = 'var(--status-warning)';
        }
    } catch (e) {
        /* Silent fallback */
    }
}

/* 4. Quick Scratchpad (Floating Markdown & Code Scratchpad) */
function initScratchpad() {
    const fab = document.getElementById('scratchpad-fab');
    const panel = document.getElementById('scratchpad-panel');
    const textarea = document.getElementById('scratchpad-textarea');
    const saveBtn = document.getElementById('scratchpad-save');
    const closeBtn = document.getElementById('scratchpad-close');
    if (!fab || !panel || !textarea) return;

    const storageKey = 'catatan_scratchpad_v1';
    textarea.value = localStorage.getItem(storageKey) || '';

    fab.addEventListener('click', () => {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
            textarea.focus();
        }
    });

    if (closeBtn) {
        closeBtn.addEventListener('click', () => panel.classList.remove('open'));
    }

    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            localStorage.setItem(storageKey, textarea.value);
            showToast('Catatan kilat tersimpan di browser!', 'success');
        });
    }

    let autoSaveTimer;
    textarea.addEventListener('input', () => {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            localStorage.setItem(storageKey, textarea.value);
        }, 1200);
    });
}

/* 5. Vault PIN Lock System (PIN Spesifik Per-Kategori, Admin Bebas Kunci) */
function initVaultPinLock() {
    const overlay = document.getElementById('vault-pin-overlay');
    if (!overlay) return; // Jika role admin, overlay tidak di-render di template

    const categorySlug = document.getElementById('category-slug')?.value || '';
    if (!categorySlug) return;

    const storageKey = `vault_unlocked_${categorySlug}`;
    if (sessionStorage.getItem(storageKey) === '1') {
        overlay.style.display = 'none';
        return;
    }

    overlay.style.display = 'flex';

    // Password PIN spesifik per-kategori sesuai instruksi
    const CATEGORY_PINS = {
        'kuliah': '081020',
        'cisco': '2007',
        'notepadpp': '2026',
        'excel': '3000',
        'word': '2027'
    };

    const targetPin = CATEGORY_PINS[categorySlug] || '2026';
    const targetLength = targetPin.length; // 6 digit untuk kuliah, 4 digit untuk lainnya

    let enteredPin = '';
    const dots = overlay.querySelectorAll('.pin-dot');
    const keys = overlay.querySelectorAll('.pin-key');
    const errorMsg = overlay.querySelector('.pin-error-msg');

    function updateDots() {
        dots.forEach((dot, i) => dot.classList.toggle('filled', i < enteredPin.length));
    }

    keys.forEach(key => {
        key.addEventListener('click', () => {
            const val = key.dataset.val;
            if (val === 'del') {
                enteredPin = enteredPin.slice(0, -1);
            } else if (val === 'lock') {
                enteredPin = '';
            } else if (enteredPin.length < targetLength) {
                enteredPin += val;
            }
            updateDots();

            if (enteredPin.length === targetLength) {
                if (enteredPin === targetPin) {
                    sessionStorage.setItem(storageKey, '1');
                    overlay.style.opacity = '0';
                    overlay.style.transition = 'opacity 300ms ease';
                    setTimeout(() => overlay.style.display = 'none', 300);
                    showToast(`Vault ${categorySlug.toUpperCase()} terbuka`, 'success');
                } else {
                    if (errorMsg) {
                        // Teks error bersih tanpa membocorkan password default
                        errorMsg.textContent = 'PIN yang Anda masukkan salah. Silakan coba lagi.';
                        errorMsg.style.display = 'block';
                    }
                    setTimeout(() => {
                        enteredPin = '';
                        updateDots();
                        if (errorMsg) errorMsg.style.display = 'none';
                    }, 1000);
                }
            }
        });
    });
}

function lockVaultCurrentCategory() {
    const categorySlug = document.getElementById('category-slug')?.value;
    if (!categorySlug) return;
    const storageKey = `vault_unlocked_${categorySlug}`;
    sessionStorage.removeItem(storageKey);
    const overlay = document.getElementById('vault-pin-overlay');
    if (overlay) {
        overlay.style.opacity = '1';
        overlay.style.display = 'flex';
        showToast('Vault berhasil dikunci kembali', 'info');
    }
}

/* 6. Multi-Tagging Berwarna */
function initFileTagging() {
    document.querySelectorAll('.add-tag-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const fileId = btn.dataset.fileId;
            openTagPopup(btn, fileId);
        });
    });

    document.querySelectorAll('.tag-chip-remove').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            e.preventDefault();
            const tagId = btn.dataset.tagId;
            const fileId = btn.dataset.fileId;
            await removeTag(fileId, tagId, btn.closest('.tag-chip'));
        });
    });
}

function openTagPopup(anchorEl, fileId) {
    document.querySelectorAll('.tag-input-popup').forEach(p => p.remove());

    const popup = document.createElement('div');
    popup.className = 'tag-input-popup open';
    popup.innerHTML = `
        <div style="margin-bottom:8px; font-size:12px; font-weight:600; color:var(--text-secondary);">Tambah Label Tag</div>
        <div style="display:flex; gap:6px; margin-bottom:8px;">
            <input type="text" id="tag-name-input" placeholder="contoh: Tugas, OSPF..." maxlength="30"
                   style="flex:1; background:var(--bg-canvas); border:1px solid var(--border-subtle); border-radius:6px; padding:0 8px; height:32px; color:var(--text-primary); font-size:12px;">
            <input type="color" id="tag-color-input" value="#e11d48" title="Pilih warna tag"
                   style="width:36px; height:32px; border:1px solid var(--border-subtle); border-radius:6px; cursor:pointer; background:var(--bg-canvas);">
        </div>
        <div style="display:flex; gap:6px;">
            <button id="tag-submit-btn" class="btn btn-primary btn-sm" style="flex:1;">Simpan</button>
            <button id="tag-cancel-btn" class="btn btn-secondary btn-sm">Batal</button>
        </div>
    `;

    anchorEl.parentElement.style.position = 'relative';
    anchorEl.parentElement.appendChild(popup);

    const nameInput = popup.querySelector('#tag-name-input');
    const colorInput = popup.querySelector('#tag-color-input');
    nameInput.focus();

    popup.querySelector('#tag-cancel-btn').addEventListener('click', () => popup.remove());
    popup.querySelector('#tag-submit-btn').addEventListener('click', async () => {
        const name = nameInput.value.trim();
        const color = colorInput.value;
        if (!name) {
            showToast('Nama tag tidak boleh kosong', 'error');
            return;
        }
        await addTag(fileId, name, color, popup);
    });

    nameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') popup.querySelector('#tag-submit-btn').click();
        if (e.key === 'Escape') popup.remove();
    });

    setTimeout(() => {
        document.addEventListener('click', function handler(e) {
            if (!popup.contains(e.target) && e.target !== anchorEl) {
                popup.remove();
                document.removeEventListener('click', handler);
            }
        });
    }, 10);
}

async function addTag(fileId, tagName, tagColor, popup) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    const formData = new FormData();
    formData.append('tag_name', tagName);
    formData.append('tag_color', tagColor);

    try {
        const res = await fetch(`/api/files/${fileId}/tags`, {
            method: 'POST',
            headers: {
                'X-CSRF-Token': csrfToken
            },
            body: formData
        });
        const data = await res.json();
        if (res.ok && data.success) {
            const tagsRow = document.querySelector(`.file-tags-row[data-file-id="${fileId}"]`);
            if (tagsRow) {
                const chip = createTagChip(data.tag, fileId);
                tagsRow.insertBefore(chip, tagsRow.querySelector('.add-tag-btn'));
            }
            if (popup) popup.remove();
            showToast(`Tag #${tagName} berhasil disematkan!`, 'success');
        } else {
            showToast(data.detail || 'Gagal menambahkan tag', 'error');
        }
    } catch (err) {
        console.error('Add tag error:', err);
        showToast('Kesalahan jaringan saat menambahkan tag', 'error');
    }
}

async function removeTag(fileId, tagId, chipEl) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
    try {
        const res = await fetch(`/api/files/${fileId}/tags/${tagId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRF-Token': csrfToken
            }
        });
        if (res.ok) {
            if (chipEl) chipEl.remove();
            showToast('Tag berhasil dihapus', 'info');
        } else {
            showToast('Gagal menghapus tag', 'error');
        }
    } catch (err) {
        console.error('Remove tag error:', err);
        showToast('Kesalahan jaringan saat menghapus tag', 'error');
    }
}

function createTagChip(tag, fileId) {
    const chip = document.createElement('span');
    chip.className = 'tag-chip';
    chip.style.cssText = `background:${tag.tag_color}22; border-color:${tag.tag_color}55; color:${tag.tag_color};`;
    chip.innerHTML = `# ${escapeHtml(tag.tag_name)} <span class="tag-chip-remove" data-tag-id="${tag.id}" data-file-id="${fileId}" title="Hapus tag">✕</span>`;
    chip.querySelector('.tag-chip-remove').addEventListener('click', async (e) => {
        e.stopPropagation();
        e.preventDefault();
        await removeTag(fileId, tag.id, chip);
    });
    return chip;
}

/* 7. Fitur View Berkas Langsung (Tanpa Perlu Unduh ke Lokal) */
function initFileViewer() {
    document.querySelectorAll('.btn-view-file').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const fileId = btn.dataset.id;
            const fileName = btn.dataset.filename;
            const ext = (btn.dataset.ext || '').toLowerCase();
            void openFileViewerModal(fileId, fileName, ext);
        });
    });
}

async function openFileViewerModal(fileId, fileName, ext) {
    let modal = document.getElementById('file-viewer-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'file-viewer-modal';
        modal.className = 'modal-backdrop';
        modal.innerHTML = `
            <div class="modal-dialog" style="max-width:920px; width:95vw; background:var(--bg-surface);">
                <div class="modal-header" style="padding:14px 20px;">
                    <div style="display:flex; align-items:center; gap:10px; overflow:hidden;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#e11d48" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                        <h3 class="modal-title" id="file-viewer-title" style="font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Lihat Berkas</h3>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                        <button type="button" class="btn btn-secondary btn-sm" id="file-viewer-copy-btn" style="display:none;">Salin Teks</button>
                        <a href="#" target="_blank" class="btn btn-secondary btn-sm" id="file-viewer-external-btn" title="Buka di Tab Baru">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                            <span>Tab Baru</span>
                        </a>
                        <button type="button" class="btn btn-ghost btn-sm" id="file-viewer-close-btn" style="padding:4px 8px; font-size:16px;">✕</button>
                    </div>
                </div>
                <div class="modal-body" id="file-viewer-body" style="padding:0; max-height:75vh; overflow:auto; background:var(--bg-canvas);">
                    <div style="padding:32px; text-align:center; color:var(--text-muted);">Memuat berkas...</div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        modal.querySelector('#file-viewer-close-btn').addEventListener('click', () => modal.classList.remove('active'));
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.classList.remove('active');
        });
    }

    const titleEl = modal.querySelector('#file-viewer-title');
    const bodyEl = modal.querySelector('#file-viewer-body');
    const copyBtn = modal.querySelector('#file-viewer-copy-btn');
    const externalBtn = modal.querySelector('#file-viewer-external-btn');

    titleEl.textContent = fileName || 'Lihat Berkas';
    const viewUrl = `/api/files/view/${fileId}`;
    externalBtn.href = viewUrl;
    copyBtn.style.display = 'none';
    bodyEl.innerHTML = '<div style="padding:32px; text-align:center; color:var(--text-muted);">Memuat berkas...</div>';

    modal.classList.add('active');

    // 1. PDF Documents
    if (ext === '.pdf') {
        bodyEl.innerHTML = `
            <iframe src="${viewUrl}" style="width:100%; height:75vh; border:none; display:block; background:#ffffff;"></iframe>
        `;
        return;
    }

    // 2. Images (PNG, JPG, JPEG)
    if (['.png', '.jpg', '.jpeg'].includes(ext)) {
        bodyEl.innerHTML = `
            <div style="padding:24px; text-align:center; display:flex; align-items:center; justify-content:center; min-height:300px;">
                <img src="${viewUrl}" alt="${escapeHtml(fileName)}" style="max-width:100%; max-height:70vh; border-radius:8px; object-fit:contain; box-shadow:var(--shadow-md);">
            </div>
        `;
        return;
    }

    // 3. Text, Scripts, Configs, Packet Tracer
    const textExts = ['.txt', '.log', '.cfg', '.conf', '.ini', '.json', '.xml', '.yml', '.md', '.py', '.sh', '.sql', '.csv', '.pkt', '.pka'];
    if (textExts.includes(ext)) {
        try {
            const res = await fetch(viewUrl);
            if (!res.ok) {
                bodyEl.innerHTML = '<div style="padding:32px; text-align:center; color:var(--status-danger);">Gagal memuat isi berkas dari server.</div>';
                return;
            }
            const textContent = await res.text();
            copyBtn.style.display = 'inline-flex';
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(textContent).then(() => {
                    showToast('Isi berkas berhasil disalin ke clipboard!', 'success');
                }).catch(err => {
                    console.error('Clipboard write error:', err);
                });
            };

            const maxLen = 80000;
            const displayStr = textContent.length > maxLen
                ? textContent.slice(0, maxLen) + '\n\n... [Konten dipotong karena ukuran besar. Buka di Tab Baru untuk melihat penuh]'
                : textContent;

            bodyEl.innerHTML = `
                <pre style="margin:0; padding:20px; font-size:12px; line-height:1.6; font-family:'Consolas','Monaco','Courier New',monospace; color:var(--text-primary); white-space:pre-wrap; word-break:break-word;">${escapeHtml(displayStr)}</pre>
            `;
            return;
        } catch (err) {
            console.error('Fetch text preview error:', err);
            bodyEl.innerHTML = '<div style="padding:32px; text-align:center; color:var(--status-danger);">Kesalahan saat membaca berkas teks.</div>';
            return;
        }
    }

    // 4. Office Documents (Word, Excel, PPT)
    bodyEl.innerHTML = `
        <div style="padding:48px 24px; text-align:center;">
            <div style="width:56px; height:56px; border-radius:var(--radius-md); background:var(--accent-subtle); border:1px solid var(--accent-border); display:flex; align-items:center; justify-content:center; margin:0 auto 16px; color:var(--accent-text);">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>
            <div style="font-size:16px; font-weight:600; color:var(--text-primary); margin-bottom:6px;">
                ${escapeHtml(fileName)}
            </div>
            <p style="color:var(--text-secondary); font-size:13px; max-width:420px; margin:0 auto 24px; line-height:1.5;">
                Berkas ${ext.toUpperCase().replace('.', '')} siap dibuka langsung di peramban Anda secara instan tanpa mengunduh ulang ke penyimpanan lokal.
            </p>
            <div style="display:inline-flex; gap:12px; align-items:center;">
                <a href="${viewUrl}" target="_blank" class="btn btn-primary">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                    <span>Buka Tampilan Dokumen</span>
                </a>
                <button type="button" class="btn btn-secondary" onclick="navigator.clipboard.writeText(window.location.origin + '${viewUrl}').then(() => showToast('Tautan langsung disalin!', 'success')).catch(err => console.error(err))">
                    Salin Tautan
                </button>
            </div>
        </div>
    `;
}

/* Initialize all enhancements */
document.addEventListener('DOMContentLoaded', () => {
    initGlobalSearch();
    initUserProfileDropdown();
    void initStorageWidget();
    initScratchpad();
    initVaultPinLock();
    initFileTagging();
    initFileViewer();
});

