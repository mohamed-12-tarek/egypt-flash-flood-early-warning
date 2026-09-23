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

---

## 4) تشغيل Kafka (نفس الأمر على أي نظام)

```bash
docker-compose up -d
```
ده بيشغّل Kafka بس على `localhost:9092`. (SQL Server منفصل — راجع الخطوة الجاية).

### إنشاء الـ topic يدويًا (مرة واحدة)
```bash
docker exec -it kafka /opt/kafka/bin/kafka-topics.sh \
  --create --topic flood-risk-raw \
  --bootstrap-server localhost:9092 \
  --partitions 3 --replication-factor 1
```

---

## 5) إعداد SQL Server المحلي بتاعك

كل فرد يستخدم نسخة SQL Server الخاصة بيه (مثبتة على الجهاز أو عبر Docker منفصل). لازم تعمل:

```sql
CREATE DATABASE FloodProjectDB;
```

---

## 6) ملف `.env`

```bash
cp .env.example .env
```

افتح `.env` واملأ بياناتك الشخصية (بورت SQL Server، اليوزر/الباسورد أو Windows Authentication، ومفتاح Groq API). التفاصيل الكاملة موجودة داخل `.env.example` نفسه كتعليقات.

⚠️ **`.env` لا يُرفع على Git أبدًا** (موجود في `.gitignore`).

تأكد إن الاتصال بقاعدة البيانات شغال:
```bash
uv run python warehouse/db_connection.py
```
المفروض يطلعلك: `✅ Connected to SQL Server successfully.`

---
