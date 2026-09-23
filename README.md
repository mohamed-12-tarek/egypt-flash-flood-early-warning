# 🌊 Flood Warning Project — Setup Guide

## 1) تثبيت `uv`

اختر الأمر حسب نظام التشغيل بتاعك:

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Linux
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### macOS
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### تأكد إن التثبيت نجح (على أي نظام)
```bash
uv --version
```

---

## 2) سحب المشروع (Clone)

نفس الأمر على الأنظمة الثلاثة:
```bash
git clone https://github.com/mohamed-12-tarek/egypt-flash-flood-early-warning.git
cd flood-warning-project
```

---

## 3) تجهيز البيئة وتثبيت المتطلبات

نفس الأوامر بالظبط على Windows وLinux وmacOS — ده بالظبط ميزة `uv`:

```bash
# يثبّت Python 3.11 تلقائيًا لو مش موجود عندك (بدون التأثير على أي إصدار تاني عندك)
uv python install 3.11

# يعمل بيئة افتراضية (.venv) مبنية على pyproject.toml
uv venv --python 3.11

# يثبّت كل المكتبات المطلوبة بنفس الإصدارات المحددة في uv.lock
uv sync
```

### تفعيل البيئة الافتراضية (خطوة يومية، مختلفة حسب النظام)

| النظام | الأمر |
|---|---|
|  Windows (PowerShell) | `.venv\Scripts\Activate.ps1` |
|  Windows (cmd) | `.venv\Scripts\activate.bat` |
|  Linux / macOS | `source .venv/bin/activate` |
