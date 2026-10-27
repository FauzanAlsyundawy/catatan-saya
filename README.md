# Catatan Saya - Personal Note Storage & Audit Vault

Aplikasi web pribadi (*single-user*) untuk manajemen penyimpanan dan pengarsipan berkas catatan (Word, Excel, Notepad++, Cisco, Kuliah) yang dilengkapi sistem audit log aktivitas *read-only* berstandar enterprise.

---

## 1. Arsitektur & Fitur Utama

- **Otentikasi & Keamanan:**
  - Password di-hash menggunakan **Argon2id** (OWASP recommendation).
  - Session cookie: `HttpOnly`, `SameSite=Strict`, `Secure` (dapat disesuaikan via `.env`).
  - Proteksi **CSRF token** untuk seluruh aksi perubahan data (*state-changing requests*).
  - **Rate Limiting Login:** Maksimal 5 kali percobaan gagal &rarr; akun/IP dikunci selama 15 menit.
  - Idle timeout sesi: **30 menit**.
  - Header keamanan: Content Security Policy (CSP) ketat, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Cache-Control: no-store` untuk seluruh halaman terautentikasi.
- **Penyimpanan Berkas:**
  - **Whitelist ekstensi:** `.doc, .docx, .xls, .xlsx, .csv, .txt, .log, .cfg, .conf, .ini, .json, .xml, .yml, .md, .pdf, .ppt, .pptx, .pkt, .pka, .zip, .png, .jpg`.
  - Berkas fisik disimpan di luar folder static (`uploads/`) menggunakan penamaan acak **UUID** untuk mencegah benturan dan *path traversal*.
  - Otomatis menangani nama berkas ganda di kategori yang sama dengan suffix `(1)`, `(2)`, dst.
  - Unduhan disajikan sebagai *stream attachment* dengan *header content disposition*.
- **Audit Log Terverifikasi (Append-Only):**
  - Mencatat otomatis: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `LOGOUT_MANUAL`, `LOGOUT_EXPIRED` (otomatis saat idle timeout habis), `UPLOAD_FILE`, dan `DELETE_FILE`.
  - Disimpan dalam format UTC di database SQLite, ditampilkan dalam **WIB (Asia/Jakarta)** dengan format Bahasa Indonesia (contoh: `26 Oktober 2026, 21:15:42 WIB`).
  - Nama berkas disimpan sebagai teks murni di log (bukan relasi) sehingga riwayat tetap abadi meskipun berkas telah dihapus.
  - Konsistensi transaksional atomik antara penghapusan file dan penulisan log audit.
- **Desain UI/UX (2026 Enterprise Aesthetic):**
  - Palet: *Dark Graphite* elegan dengan SATU warna aksen *Crimson Red* (`#e11d48`) yang diselaraskan dengan logo.
  - Ikon inline SVG Lucide mandiri (tanpa dependensi CDN eksternal).
  - Beranda bergaya *Bento Grid* untuk 5 kategori tetap (`word`, `excel`, `notepadpp`, `cisco`, `kuliah`).
  - Halaman login dengan animasi *fade-in* logo, tombol intip/sembunyikan password, dan pesan error generik.
  - Dialog konfirmasi hapus modal dan notifikasi toast.
  - Responsif penuh (*desktop sidebar* & *mobile drawer*).

---

## 2. Struktur Direktori

```text
NOTE ENTERPRISE/
├── app/
│   ├── routers/
│   │   ├── auth.py          # Autentikasi, login/logout, rate limiter
│   │   ├── dashboard.py     # Beranda bento grid 5 kategori
│   │   ├── files.py         # Multi-file upload, streaming download, delete
│   │   └── audit.py         # Audit log table, filter & pagination
│   ├── utils/
│   │   ├── storage.py       # Sanitasi nama, suffix ganda, sizing, ikon
│   │   └── timezone.py      # Konversi UTC ke WIB Bahasa Indonesia
│   ├── config.py            # Konfigurasi Pydantic dari .env
│   ├── database.py          # SQLite WAL-mode connection & migrations
│   ├── dependencies.py      # Session validator & CSRF checks
│   ├── main.py              # Inisialisasi FastAPI & middleware keamanan
│   └── security.py          # Argon2id hashing, session token, audit writer
├── assets/
│   └── logo.png             # Logo asli aplikasi (digunakan juga sebagai favicon)
├── data/
│   └── app.db               # Database SQLite (dikecualikan dari Git)
├── uploads/                 # Berkas fisik berpenamaan UUID (dikecualikan dari Git)
├── static/
│   ├── css/style.css        # Design system Vanilla CSS (Dark Graphite + Crimson Red)
│   └── js/
│       ├── app.js           # Toast, modal konfirmasi, drawer mobile, toggle password
│       └── upload.js        # Drag-and-drop & XMLHttpRequest progress bar
├── templates/
│   ├── base.html            # Layout utama, sidebar desktop, drawer mobile
│   ├── login.html           # Layar masuk dengan fade-in logo
│   ├── dashboard.html       # Bento grid 5 kategori dan metrik kapasitas
│   ├── category.html        # Upload dropzone & tabel berkas
│   └── audit_log.html       # Tabel audit log append-only & filter
├── tests/
│   └── test_app.py          # Automated test suite (Pytest)
├── create_admin.py          # Skrip CLI interaktif pembuatan admin
├── requirements.txt         # Dependensi Python
├── .env.example             # Template variabel lingkungan
├── .gitignore               # Konfigurasi pengabaian file Git
└── README.md
```

---

## 3. Prasyarat Sistem

- Python 3.11 atau lebih baru (Diuji pada Python 3.13)
- Windows PowerShell atau Terminal Linux/macOS

---

## 4. Instalasi & Setup

### Langkah 1: Buat Virtual Environment & Pasang Dependensi

Buka terminal di direktori proyek:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

*(Untuk Linux/macOS, gunakan `source .venv/bin/activate`)*

### Langkah 2: Salin File Konfigurasi Lingkungan

```powershell
Copy-Item .env.example .env
```

Sesuaikan isi `.env` sesuai kebutuhan. Untuk lingkungan pengujian lokal (HTTP), pastikan `SESSION_COOKIE_SECURE=false`. Jika disebarkan di balik reverse proxy HTTPS (Nginx/Caddy), ubah menjadi `SESSION_COOKIE_SECURE=true`.

---

## 5. Membuat Akun Administrator

Jalankan skrip CLI interaktif untuk membuat username dan password admin pertama kali:

```powershell
python create_admin.py
```

Masukkan username dan password (minimal 8 karakter). Password akan di-hash menggunakan Argon2id dan disimpan secara aman ke basis data `data/app.db`.

---

## 6. Menjalankan Aplikasi

Jalankan server menggunakan Uvicorn:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Buka browser pada: **<http://127.0.0.1:8000>**

---

## 7. Menjalankan Automated Test Suite

Untuk memverifikasi fungsionalitas, keamanan hashing Argon2id, pembatasan rate limit, header CSP, filter whitelist upload, dan konsistensi log audit:

```powershell
python -m pytest -v tests/test_app.py
```

---

## 8. Prosedur Pencadangan (Backup) & Pemulihan (Disaster Recovery)

Karena aplikasi menggunakan SQLite dan penyimpanan berkas berbasis file terpisah:

1. **Pencadangan Database:**
   Salin file `data/app.db` saat server berhenti atau gunakan perintah SQLite backup:

   ```powershell
   Copy-Item data\app.db backup\app_$(Get-Date -Format 'yyyyMMdd_HHmmss').db
   ```

2. **Pencadangan Berkas Fisik:**
   Arsipkan seluruh isi folder `uploads/`:

   ```powershell
   Compress-Archive -Path uploads\* -DestinationPath backup\uploads_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip
   ```

3. **Pemulihan (Restore):**
   Cukup letakkan kembali file `app.db` ke direktori `data/` dan ekstrak berkas fisik ke direktori `uploads/`.
