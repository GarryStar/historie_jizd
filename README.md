# Kniha jízd 🚗

Jednoduchá webová aplikace pro správu knihy jízd s podporou:
- registrace přes e-mail
- obnovy hesla
- offline ukládání jízd
- synchronizace po návratu online
- správy vozidel
- historie jízd

Aplikace je postavená v Python Flask + SQLite + čistý HTML/CSS/JavaScript.

---

# Funkce

## 🔐 Autentizace

- přihlášení uživatele
- registrace přes e-mailový odkaz
- obnova hesla přes e-mail
- token-based autentizace

## 🚘 Vozidla

- přidání vozidla
- evidence tachometru
- více vozidel na uživatele

## 🛣️ Jízdy

- start / stop režim jízdy
- uložení města startu a cíle
- výpočet ujeté vzdálenosti
- uchování rozjeté jízdy i po reloadu stránky
- offline režim

## 📡 Offline režim

- rozjetá jízda se ukládá do localStorage
- jízdy se ukládají i bez internetu
- po návratu online proběhne automatická synchronizace

---

# Použité technologie

## Backend

- Python 3
- Flask
- SQLite
- bcrypt
- python-dotenv
- itsdangerous

## Frontend

- HTML5
- CSS3
- Vanilla JavaScript

---

# Instalace

## 1. Klonování repozitáře

```bash
git clone https://github.com/tvoje-jmeno/kniha-jizd.git
cd kniha-jizd
```

---

## 2. Vytvoření virtuálního prostředí

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Instalace balíčků

```bash
pip install -r requirements.txt
```

---

# Konfigurace

Vytvoř soubor:

```txt
.env
```

a vlož:

```env
SECRET_KEY=tvoje_tajne_heslo

MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_USERNAME=tvuj.email@gmail.com
MAIL_PASSWORD=tvoje_app_password
MAIL_FROM=tvuj.email@gmail.com

APP_URL=http://localhost:5000
```

---

# Spuštění aplikace

```bash
python app.py
```

Aplikace poběží na:

```txt
http://localhost:5000
```

---

# Struktura projektu

```txt
kniha-jizd/
│
├── app.py
├── requirements.txt
├── .env
│
├── instance/
│   └── kniha_jizd.db
│
├── static/
│   ├── style.css
│   └── app.js
│
├── templates/
│   ├── index.html
│   ├── dashboard.html
│   ├── vozidla.html
│   ├── historie.html
│   ├── nova_jizda.html
│   ├── reset_hesla.html
│   └── dokoncit_registraci.html
│
└── README.md
```

---

# Databáze

Použitá databáze:

```txt
SQLite
```

Tabulky:
- users
- vehicles
- trips

Databázový soubor:

```txt
instance/kniha_jizd.db
```

---

# Bezpečnost

- hesla jsou hashována pomocí bcrypt
- reset hesla používá časově omezené tokeny
- registrační odkazy mají expiraci
- autentizace probíhá přes Bearer token

---

# Offline režim

Aplikace využívá:

```txt
localStorage
```

pro:
- rozjetou jízdu
- offline uložené jízdy
- synchronizační frontu

---

# Plánované funkce

- GPS město automaticky
- PWA instalace
- export PDF / Excel
- mapa trasy
- synchronizace historie
- více uživatelských rolí
- cloud backup

---

# Autor

Projekt vzniká jako hobby projekt pro evidenci jízd a experimentování s Flask aplikací, offline režimem a UX návrhem.