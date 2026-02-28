# 📊 Forex Trading Signal Dashboard (Python/Flask)

Dashboard trading multi-timeframe dengan analisis **BBMA**, **SMC**, **Currency Strength**, dan **Volume Delta**.

---

## 🚀 Cara Menjalankan

### 1. Install Dependencies

```bash
cd forex-dashboard-python
pip install -r requirements.txt
```

### 2. Jalankan Server

```bash
python app.py
```

### 3. Buka di Browser

```
http://localhost:5000
```

Dashboard akan otomatis redirect ke halaman BBMA.

---

## 📡 Mode Data: Simulasi vs Real-Time MT5

Dashboard ini mendukung **2 mode data**:

### Mode Simulasi (Default)
- Aktif otomatis jika MetaTrader5 **tidak terinstall** atau **tidak running**
- Data signal di-generate menggunakan seeded random (berubah setiap 5 menit)
- Badge **SIMULATED** muncul di navbar
- Cocok untuk testing dan demo

### Mode Real-Time (MetaTrader5)
- Aktif otomatis jika MT5 terminal **running dan login**
- Data OHLCV dan tick volume diambil langsung dari MT5
- Signal BBMA dihitung dari **Bollinger Bands + Moving Average** real
- Signal SMC dihitung dari **swing points, order blocks, FVG** real
- Volume Delta menggunakan **tick volume** real dari MT5
- Badge **MT5 LIVE** muncul di navbar (hijau, berkedip)

### Cara Mengaktifkan Mode Real-Time

1. **Install MetaTrader5 Terminal** di PC (download dari broker)
2. **Login** ke akun trading (demo atau live)
3. **Install package Python MT5**:
   ```bash
   pip install MetaTrader5
   ```
4. **Jalankan ulang** `python app.py`
5. Jika koneksi berhasil, akan muncul log:
   ```
   MT5 connected: MetaTrader 5 (build XXXX)
   ```

> ⚠️ **Catatan**: Package `MetaTrader5` hanya tersedia di **Windows** dan membutuhkan MT5 terminal yang sudah terinstall.

---

## 📄 Halaman Dashboard

| Halaman | URL | Deskripsi |
|---------|-----|-----------|
| **BBMA** | `/bbma` | Bollinger Band + MA — Combo setup (REM, REE, RME, ZZL, Diamond) & single TF signals |
| **SMC** | `/smc` | Smart Money Concept — Market structure, bias, BOS, CHoCH, OB, FVG, Liquidity |
| **Summary** | `/summary` | Currency Strength — Ranking kekuatan mata uang (gabungan BBMA + SMC) |
| **Volume Delta** | `/volume-delta` | Volume Delta — Tekanan beli/jual per currency & per pair |

---

## 🔌 API Endpoints (JSON)

Digunakan oleh frontend untuk auto-refresh setiap 5 menit:

| Endpoint | Deskripsi |
|----------|-----------|
| `GET /api/bbma-signals` | Data signal BBMA (combo + single TF) |
| `GET /api/smc-signals` | Data signal SMC (structure + bias + entry) |
| `GET /api/currency-strength` | Ranking kekuatan mata uang |
| `GET /api/volume-delta` | Analisis volume delta per pair & currency |

---

## 📁 Struktur Project

```
forex-dashboard-python/
├── app.py                           # Flask app + routes + template filters
├── requirements.txt                 # Dependencies
├── services/
│   ├── mt5_data_service.py          # Koneksi MT5 + fallback ke simulasi
│   ├── bbma_signal_service.py       # Logika signal BBMA
│   ├── smc_signal_service.py        # Logika signal SMC
│   ├── currency_strength_service.py # Aggregasi kekuatan mata uang
│   └── volume_delta_service.py      # Analisis volume delta
├── templates/
│   ├── layouts/base.html            # Layout utama (navbar + refresh timer)
│   └── dashboard/
│       ├── bbma.html
│       ├── smc.html
│       ├── summary.html
│       └── volume_delta.html
└── static/
    ├── css/dashboard.css            # Dark theme premium
    └── js/dashboard.js              # Auto-refresh + live update
```

---

## ⚙️ Requirements

- **Python** 3.10+
- **Flask** 3.0+
- **NumPy** 1.24+
- **MetaTrader5** 5.0+ *(opsional, untuk data real-time)*
- **OS**: Windows *(wajib jika menggunakan MT5)*
