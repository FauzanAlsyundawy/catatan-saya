/**
 * Catatan Saya - Multi-File Upload Manager
 * Drag-and-drop, multi-file queue, real-time XMLHttpRequest progress bar.
 */

document.addEventListener('DOMContentLoaded', () => {
    initUploadDropzone();
});

function initUploadDropzone() {
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-input');
    const queueContainer = document.getElementById('upload-queue');
    if (!dropzone || !fileInput) return;

    // Click to select files
    dropzone.addEventListener('click', (e) => {
        // Prevent click loop if clicking input directly
        if (e.target !== fileInput) {
            fileInput.click();
        }
    });

    // Drag & drop events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-over');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            handleFilesSelected(files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFilesSelected(fileInput.files);
            // Reset input value so same files can be selected again if needed
            fileInput.value = '';
        }
    });
}

async function handleFilesSelected(fileList) {
    const categorySlug = document.getElementById('category-slug')?.value;
    if (!categorySlug) {
        showToast('Kategori tidak ditemukan', 'error');
        return;
    }

    const queueContainer = document.getElementById('upload-queue');
    const files = Array.from(fileList);

    // Whitelist check from data attribute if available
    const allowedExtsAttr = document.getElementById('allowed-extensions')?.value || '';
    const allowedExts = allowedExtsAttr.split(',').map(s => s.trim().toLowerCase());
    const maxSizeBytes = 50 * 1024 * 1024; // 50 MB

    for (const file of files) {
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        
        // Whitelist check
        if (allowedExts.length > 0 && !allowedExts.includes(ext)) {
            showToast(`File "${file.name}" ditolak: ekstensi ${ext} tidak diizinkan.`, 'error');
            continue;
        }

        // Max size check
        if (file.size > maxSizeBytes) {
            showToast(`File "${file.name}" melebihi batas maksimal 50 MB.`, 'error');
            continue;
        }

        // Upload single file with progress
        await uploadSingleFile(file, categorySlug, queueContainer);
    }

    // Refresh page after all uploads finished
    setTimeout(() => {
        window.location.reload();
    }, 600);
}

function uploadSingleFile(file, categorySlug, queueContainer) {
    return new Promise((resolve) => {
        const queueCard = document.createElement('div');
        queueCard.className = 'upload-queue-card';

        const queueId = 'queue-' + Math.random().toString(36).substring(2, 9);
        queueCard.id = queueId;

        const sizeFormatted = formatBytes(file.size);

        queueCard.innerHTML = `
            <div class="upload-queue-meta">
                <span style="font-weight: 500; color: var(--text-primary);">${escapeHtml(file.name)}</span>
                <span id="${queueId}-status" style="color: var(--text-muted); font-size: 11px;">0% (${sizeFormatted})</span>
            </div>
            <div class="progress-track">
                <div id="${queueId}-bar" class="progress-bar-fill"></div>
            </div>
        `;

        if (queueContainer) {
            queueContainer.appendChild(queueCard);
        }

        const bar = document.getElementById(`${queueId}-bar`);
        const status = document.getElementById(`${queueId}-status`);

        const xhr = new XMLHttpRequest();
        const formData = new FormData();
        formData.append('file', file);
        formData.append('category_slug', categorySlug);

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

        xhr.open('POST', '/api/files/upload', true);
        xhr.setRequestHeader('X-CSRF-Token', csrfToken);
        xhr.setRequestHeader('Accept', 'application/json');

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                if (bar) bar.style.width = `${percent}%`;
                if (status) status.textContent = `${percent}% (${sizeFormatted})`;
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                try {
                    const res = JSON.parse(xhr.responseText);
                    if (bar) {
                        bar.style.width = '100%';
                        bar.style.backgroundColor = 'var(--status-success)';
                    }
                    if (status) {
                        status.textContent = 'Berhasil diunggah';
                        status.style.color = 'var(--status-success)';
                    }
                    showToast(`"${res.file.original_filename}" berhasil diunggah!`, 'success');
                } catch (e) {
                    showToast(`"${file.name}" berhasil diunggah`, 'success');
                }
            } else {
                let errText = 'Gagal mengunggah file';
                try {
                    const errRes = JSON.parse(xhr.responseText);
                    if (errRes.detail) errText = errRes.detail;
                } catch (e) {}

                if (bar) {
                    bar.style.backgroundColor = 'var(--status-danger)';
                }
                if (status) {
                    status.textContent = 'Gagal';
                    status.style.color = 'var(--status-danger)';
                }
                showToast(`"${file.name}": ${errText}`, 'error');
            }
            resolve();
        };

        xhr.onerror = () => {
            if (status) {
                status.textContent = 'Kesalahan Jaringan';
                status.style.color = 'var(--status-danger)';
            }
            showToast(`Kesalahan jaringan saat mengunggah "${file.name}"`, 'error');
            resolve();
        };

        xhr.send(formData);
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
