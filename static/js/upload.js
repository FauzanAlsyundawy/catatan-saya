/**
 * Catatan Saya - Multi-File Upload Manager
 * Drag-and-drop, multi-file queue, real-time XMLHttpRequest progress bar.
 */

let uploadQueueCounter = 0;

document.addEventListener('DOMContentLoaded', () => {
    initUploadDropzone();
});

function initUploadDropzone() {
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-input');
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
            void handleFilesSelected(files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            void handleFilesSelected(fileInput.files);
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

    let anySuccess = false;

    // Sequential queue processor avoids 'await' inside loop (SonarLint S9382)
    const processUploadQueue = async (index) => {
        if (index >= files.length) return;
        const file = files[index];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        if (allowedExts.length > 0 && !allowedExts.includes(ext)) {
            showToast(`File "${file.name}" ditolak: ekstensi ${ext} tidak diizinkan.`, 'error');
        } else if (file.size > maxSizeBytes) {
            showToast(`File "${file.name}" melebihi batas maksimal 50 MB.`, 'error');
        } else {
            const ok = await uploadSingleFile(file, categorySlug, queueContainer);
            if (ok) anySuccess = true;
        }

        await processUploadQueue(index + 1);
    };

    await processUploadQueue(0);

    // Only refresh page if at least one upload succeeded
    if (anySuccess) {
        setTimeout(() => {
            window.location.reload();
        }, 800);
    }
}

function handleUploadSuccess(responseText, file, bar, status, resolve) {
    if (bar) {
        bar.style.width = '100%';
        bar.style.backgroundColor = 'var(--status-success)';
    }
    if (status) {
        status.textContent = 'Berhasil diunggah';
        status.style.color = 'var(--status-success)';
    }
    try {
        const res = JSON.parse(responseText);
        showToast(`"${res.file.original_filename}" berhasil diunggah!`, 'success');
    } catch (err) {
        console.warn('Upload response JSON parse warning:', err);
        showToast(`"${file.name}" berhasil diunggah`, 'success');
    }
    resolve(true);
}

function handleUploadFailure(responseText, file, bar, status, resolve) {
    let errText = 'Gagal mengunggah file';
    try {
        const errRes = JSON.parse(responseText);
        if (errRes.detail) errText = errRes.detail;
    } catch (err) {
        console.warn('Upload error response JSON parse warning:', err);
    }

    if (bar) {
        bar.style.backgroundColor = 'var(--status-danger)';
    }
    if (status) {
        status.textContent = 'Gagal';
        status.style.color = 'var(--status-danger)';
    }
    showToast(`"${file.name}": ${errText}`, 'error');
    resolve(false);
}

function uploadSingleFile(file, categorySlug, queueContainer) {
    return new Promise((resolve) => {
        const queueCard = document.createElement('div');
        queueCard.className = 'upload-queue-card';

        // Deterministic collision-safe ID without pseudo-random generator (SonarLint S2245)
        uploadQueueCounter += 1;
        const queueId = `queue-${Date.now()}-${uploadQueueCounter}`;
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
                handleUploadSuccess(xhr.responseText, file, bar, status, resolve);
            } else {
                handleUploadFailure(xhr.responseText, file, bar, status, resolve);
            }
        };

        xhr.onerror = () => {
            if (status) {
                status.textContent = 'Kesalahan Jaringan';
                status.style.color = 'var(--status-danger)';
            }
            showToast(`Kesalahan jaringan saat mengunggah "${file.name}"`, 'error');
            resolve(false);
        };

        xhr.send(formData);
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
