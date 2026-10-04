# 🌊 Egypt Flash Flood Early Warning

نظام إنذار مبكر للسيول المفاجئة في مصر.
ده ياشباب كل حاجه بالتفصيل طريقه التعامل عباره عن 3 حاجات بالترتيب:

1. **الجزء 1:** إيه اللي تثبّته على جهازك (مرة واحدة)
2. **الجزء 2:** أول تشغيل للمشروع (مرة واحدة)
3. **الجزء 3:** الأوامر اللي بتستخدمها **كل يوم**

> كل الأوامر بتتكتب في **PowerShell** من جوه فولدر المشروع في vs code في ال terminal يعني [ctrl + ذ].

---

# الجزء 1: إيه اللي لازم تثبّته الأول

| #   | البرنامج                  | ليه؟                               | تتأكد إنه اتثبّت   |
| --- | ------------------------- | ---------------------------------- | ------------------ |
| 1   | **Git**                   | تسحب المشروع                       | `git --version`    |
| 2   | **Docker Desktop**        | بيشغّل Kafka وAirflow              | `docker --version` |
| 3   | **SQL Server** + **SSMS** | قاعدة بيانات المشروع (Warehouse)   | افتح SSMS واتصل    |
| 4   | **uv**                    | لو هتشغّل سكريبتات Python من جهازك | `uv --version`     |

### تثبيت Git
نزّله من https://git-scm.com/download/win وكمّل Next.

### تثبيت Docker Desktop
1. نزّله من https://www.docker.com/products/docker-desktop وثبّته.
2. افتحه واستنى لحد ما تشوف **"Engine running"** تحت على الشمال.
3. من Settings ← Resources: خلّي الذاكرة **4 GB على الأقل**.

### تثبيت SQL Server
نزّل **SQL Server Developer** (مجاني) و**SSMS** من موقع Microsoft، وثبّتهم.
بعد التثبيت لازم تظبّط 3 حاجات (هنعملها في الجزء 2، الخطوة 2).

### تثبيت uv (اختياري)
مش لازم عشان تشغّل Airflow (uv بيتثبّت لوحده جوه Docker).
محتاجه بس لو هتكتب كود وتجرّبه على جهازك:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
اقفل PowerShell وافتحه تاني، وبعدين `uv --version`.

---

# الجزء 2: أول تشغيل (مرة واحدة بس)

## الخطوة 1: اسحب المشروع
```powershell
git clone https://github.com/mohamed-12-tarek/egypt-flash-flood-early-warning.git
cd egypt-flash-flood-early-warning
```

## الخطوة 2: جهّز SQL Server

**أ) شغّل الخدمة** (افتح PowerShell بـ *Run as administrator*):
```powershell
Start-Service MSSQLSERVER
Set-Service MSSQLSERVER -StartupType Automatic
```

**ب) فعّل TCP/IP على بورت 1433:**
1. اضغط Win+R واكتب `SQLServerManager16.msc` (لو مفتحش جرّب `15` أو `17`).
2. `SQL Server Network Configuration` ← `Protocols for MSSQLSERVER`.
3. كليك يمين على **TCP/IP** ← **Enable**.
4. كليك يمين ← **Properties** ← تبويب **IP Addresses** ← انزل لآخر حاجة **IPAll**:
   - `TCP Dynamic Ports` → امسحها (خليها فاضية)
   - `TCP Port` → اكتب `1433`
5. `SQL Server Services` ← كليك يمين على **SQL Server** ← **Restart**.


**د) افتح (PowerShell كـ Administrator):
```powershell
New-NetFirewallRule -DisplayName "SQL Server 1433" -Direction Inbound -Protocol TCP -LocalPort 1433 -Action Allow
```

**هـ) اتأكد:**
```powershell
Test-NetConnection -ComputerName localhost -Port 1433
```
لازم تلاقي `TcpTestSucceeded : True`.

## الخطوة 3: ملف `.env`
```powershell
copy .env.example .env
```

فتح ملف ال .env و
غيّر السطرين دول بس (الباقي سيبه):
```
SQLSERVER_PASSWORD=الباسورد_بتاع_sa
GROQ_API_KEY=مفتاحك_من_Groq
```
>ال GROQ_API_KEY سيبه فاضي زي مهو انا هديهولك في نهايه المشروع او هخليك تجيب واحد بس في الاخر
>اتاكد ان ال **SQLSERVER_PASSWORD** اللي انت هتكتبه هو فعلا الباسورد الصحيح اللي انت عملته و انت بتسطب sql server اول مره علشان ميحصلشي معاك اي مشكله دب لو نسيته خش ل claude قله:

```
انا نسيت ال password بتاع ال sa user , عايز اغيره من sql server باستخدام ال queries
```
هيديك 2 queries نفذهم و حط فيهم الباسورد اللي انت عايزه و ده نفسه اللي هتستخدمه في ل .env
⚠️ ملف `.env` ده بتاعك لوحدك. **عمره ما يتبعت ولا يتعمله commit.**
> ⚠️ متكتبش `"` ولا `$` في الباسورد.

## الخطوة 4: شغّل الـContainers
اتأكد إن Docker Desktop شغال يعني [ُEngine Running]
زي ما انت شايف تحت علي الشمال خالص

![[Pasted image 20261004103450.png]]

 وبعدين:
```powershell
docker compose up -d --build
```
- أول مرة هياخد **5 لـ15 دقيقة**. استنى ومتقفلش PowerShell ومتعيدش الأمر.
- بعد ما يخلص اتأكد:
```powershell
docker ps
```
لازم تشوف 3 كونتينرات: `kafka` و`airflow-db` (healthy) و`airflow` هتلاقي الاسماء دي مكتوبه في اقصي اليمين.

## الخطوة 5: ثبّت مكتبات Python جوه Airflow
```powershell
docker exec -u root airflow chown -R airflow /opt/uv-venv

docker exec -u airflow -e UV_PROJECT_ENVIRONMENT=/opt/uv-venv -e UV_HTTP_TIMEOUT=600 -e UV_LINK_MODE=copy airflow bash -c "cd /opt/airflow/project && python -m uv sync > /tmp/uv_sync.log 2>&1"

```
كل امر و التاني انا فاصل بينهم ب line فاضي خد بالك و ده بيشتغل في ال front قدامك متعملوش deattatch علشان تشوف بس اللي بيحصل بياخد **10 لـ20 دقيقة** انا بقول بالوقت ياشباب علشان متفكروش انه عطلان او وقف.

لما تلاقي سطر فيه `Installed ... packages` يبقى خلص اعمل بقي [ctrl + c].
اتأكد:
```powershell
docker exec -u airflow airflow /opt/uv-venv/bin/python -c "import kafka, pandas, pyodbc; print('OK')"
```
لازم يطبع `OK`.

> ⚠️ أثناء الخطوة دي **متعملش** `docker compose up` ولا Restart للكونتينر.

## الخطوة 6: افتح Airflow
1. هتعمل run لل command ده:
```
docker exec airflow curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/health 
```
لو لقيت الخرج بتاعه 000 استني شويه دقيقه كده ول حاجه و جرب تاني لحد ميرجعلك 200.

2. بعدين افتح المتصفح على **http://localhost:8080**.
3. اليوزر: `admin`
4. هات الباسورد بالأمر ده اكتبه بردك في ال terminal بتاع vs code:
```powershell
docker exec airflow cat /opt/airflow/standalone_admin_password.txt
```

## الخطوة 7: شغّل تحميل البيانات (مرة واحدة)
1. في الصفحة الرئيسية، دوس على ▶ جنب **`historical_bootstrap`** ← **Trigger DAG**.
2. . و بعدين تعال علي 3 نقط اللي علي اليمين و اختار graphs و استنى لحد ما التاسكات التلاتة يبقوا **أخضر** (بياخد 3-4 دقايق):
   `setup_db` ← `fetch_static_data` ← `fetch_historical`
3. لو تاسك بقى **أحمر**: دوس عليه ← **Logs** ← وابعت الخطأ للتيم او ل claude. لو الخطأ `429 Too Many Requests` استنى دقيقة ودوس **Clear** على التاسك.

## الخطوة 8: اتأكد إن البيانات وصلت
افتح sql server و اعمل new query و نفذ ال queries دي:
```sql
SELECT COUNT(*) FROM FloodProjectDB.gold.dim_location;           -- 15
SELECT city, COUNT(*) FROM FloodProjectDB.bronze.historical_weather GROUP BY city;  -- 15 مدينة
```

![[Screenshot 2026-10-04 095911.png]]
## الخطوة 9: الـ Hourly
الـDAG اسمه **`hourly_ingestion`** وبيشتغل **لوحده كل ساعة**، مش محتاج تعمل حاجة.
للتجربة فوراً: دوس ▶ ← **Trigger DAG**، وبعدها بردك اتاكد في sql server:

```sql

SELECT TOP 20 * FROM FloodProjectDB.bronze.live_weather ORDER BY ingested_at DESC;
```

![[Screenshot 2026-10-04 095414.png]]

✅كده المشروع شغال. الجزء الجاي هو اللي هتستخدمه كل يوم.

---

# الجزء 3: كل يوم لما تيجي تشتغل

## لما تفتح الجهاز (أو بعد Restart)

الكونتينرات بتقف لما الجهاز يقفل. افتحهم بالترتيب ده:

**1)** افتح **Docker Desktop** واستنى لحد ما يقول **Engine running**.

**2)** اتأكد إن SQL Server شغال:
```powershell
Get-Service MSSQLSERVER
```
لو `Stopped` (افتح PowerShell كـ Administrator):
```powershell
Start-Service MSSQLSERVER
```

**3)** روح لفولدر المشروع وشغّل:
```powershell
cd egypt-flash-flood-early-warning
docker compose up -d
```

**4)** استنى **2 لـ3 دقايق** وافتح **http://localhost:8080**.

ده كل حاجة. البيانات ومكتبات Python محفوظة، مش محتاج تعيد أي خطوة من الجزء 2.

## لما تخلص شغل

مش لازم تعمل حاجة، تقدر تقفل الجهاز عادي. لو عايز تقفل المشروع صح:
```powershell
docker compose stop
```

## أوامر مفيدة

| عايز | الأمر |
|---|---|
| تشوف الكونتينرات شغالة ولا لأ | `docker ps` |
| تشوف لوج Airflow | `docker logs airflow --tail 30` |
| تعمل Restart لـ Airflow بس | `docker restart airflow` (واستنى دقيقتين) |
| تنسى الباسورد | `docker exec airflow cat /opt/airflow/standalone_admin_password.txt` |
| تشوف DAGs فيها أخطاء | `docker exec -u airflow airflow airflow dags list-import-errors` |
| تسحب آخر تحديثات الفريق | `git pull` |
| لو حد غيّر `Dockerfile` أو `docker-compose.yml` | `docker compose up -d --build` |

## ⛔ أوامر متعملهاش

| الأمر | ليه؟ |
|---|---|
| `docker compose down -v` | بيمسح مكتبات Python وبيانات Airflow، وهتعيد الخطوة 5 |
| `docker compose up` وإنت شايف إن لسه بيقلّع | بيقطع التهيئة ويبوّظها |
| مشاركة ملف `.env` | فيه الباسورد ومفتاح Groq |

---

# 🛠️ لو حصلت مشكلة

| المشكلة | الحل |
|---|---|
| `http://localhost:8080` فاضية | استنى 2-5 دقايق، وبعدين `docker logs airflow --tail 20` |
| تاسك فشل بـ `Login timeout expired` | SQL Server واقف أو TCP/IP مش مفعّل: راجع الخطوة 2 |
| تاسك فشل بـ `Login failed for user 'sa'` | الباسورد في `.env` غلط، أو دخول SQL مش مفعّل |
| تاسك فشل بـ `ModuleNotFoundError` | أعد الخطوة 5 |
| تاسك واقف `queued` ومش بيبدأ | `docker restart airflow` واستنى 3 دقايق |
| تاسك `ensure_topic` فشل | `docker compose up -d kafka` وأعد التاسك |
| `Cannot open service MSSQLSERVER` | افتح PowerShell بـ *Run as administrator* |
| `port is already allocated` | برنامج تاني ماسك البورت (8080 أو 19092): اقفله |
| `airflow-db` مش healthy | استنى دقيقتين. لو لسه: `docker compose down` ثم `docker volume rm egypt-flash-flood-early-warning_airflow-pg` ثم `docker compose up -d` |

---

# 📁 ملفات لازم تكون موحوده في المشروع

لازم تتاكد انه .gitignore عندك و فيه المحتوي ده و لو في حاجه في شغلك مش عايزها تطلع علي repo ضيفها هنا
`.gitignore` يكون فيه:
```
.env
.venv/
__pycache__/
logs/
```

`Dockerfile`:
```dockerfile
FROM apache/airflow:2.10.2-python3.11

USER root
RUN apt-get update && apt-get install -y curl gnupg unixodbc-dev \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
 && mkdir /opt/uv-venv && chown airflow /opt/uv-venv

USER airflow
RUN pip install --no-cache-dir -U uv
```

`.dockerignore`:
```
.venv
__pycache__
logs
.git
```
