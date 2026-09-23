# 🏗️ Architecture
### Egypt Flash Flood Early Warning System

---

## 1) نظرة عامة

نظام لرصد وتوقع مخاطر السيول المفاجئة في 15 منطقة مصرية معرضة للخطر، باستخدام بيانات طقس حية، معالجة Big Data (Spark)، نموذج Machine Learning، وChatbot مبني على LangChain.

---

## 2) الـ Tech Stack

| الطبقة | الأداة |
|---|---|
| مصدر البيانات | Open-Meteo API (طقس) + Open-Elevation API (ارتفاع) |
| نقل البيانات اللايف | Apache Kafka (محلي عبر Docker) |
| المعالجة | Apache Spark (PySpark محلي) |
| التخزين | SQL Server (محلي عبر Docker) |
| التوقع | XGBoost |
| الذكاء التوليدي | LangChain + Chroma + Groq API |
| الـ Backend APIs | FastAPI |
| الـ Frontend | React |
| بيئة Python | 3.11، مُدارة عبر `uv` |

> **ملاحظة:** المعمارية مصممة لتكون Cloud-Portable — قابلة للنقل مستقبلًا لـ Azure (Event Hubs بدل Kafka، Azure SQL بدل SQL Server المحلي، Databricks بدل Spark المحلي) بدون تغيير في منطق الكود.

---

## 3) الطبقات بالتفصيل

راجع `docs/data_contract.md` للحصول على تفاصيل كل جدول وعمود بالضبط.

| الطبقة | الوصف المختصر |
|---|---|
| **Bronze** | بيانات خام كما وصلت من المصدر، بدون أي معالجة |
| **Silver** | بيانات منظفة + مُثراة (join مع dim_location) + كل الـ engineered features |
| **Gold** | جداول جاهزة للاستهلاك: `dim_location`, `fact_hourly_risk`, `predictions` |

### مسارات تنفيذ Spark (مسار واحد بمنطق مشترك)
- **Historical Bootstrap** (مرة واحدة): يقرأ كل `bronze/historical/` → يكتب Silver بالكامل (Full Load)
- **Live Incremental** (كل ساعة): يقرأ الساعة الجديدة + آخر 72 ساعة من Silver (للـ context) → يضيف صف واحد جديد (Append)
- الدالتين بيستخدموا نفس ملف `shared_feature_logic.py` لضمان اتساق الحسابات بين المسارين.

### دورة الموديل
- **Inference** (كل ساعة): يقرأ صف واحد جاهز من `gold.fact_hourly_risk` (فيه كل الـ features already computed) → `predict()` → يكتب في `gold.predictions`
- **Retraining** (أسبوعيًا): يتدرب على كل تاريخ `silver.fact_weather_features` → يقارن بالموديل الحالي (Champion vs Challenger) → يحتفظ بالأفضل فقط

---

## 4) توزيع المسؤوليات

راجع `Team_Tasks_And_Warehouse_Reference.md` للتفاصيل الكاملة لكل شخص. ملخص سريع:

| الشخص | المسؤولية |
|---|---|
| محمد طارق | Ingestion (Static + Historical + Live) + LangChain |
| منه وخيري | Data Warehouse (Schema + Data Contract) |
| يوسف | Spark Jobs + React Frontend |
| عمرو | Analysis + APIs |
| عبد الرحمن | Machine Learning |

---

## 5) بيئة التشغيل المحلية

```
Docker Compose → Kafka + SQL Server
                        │
              Python 3.11 (uv) → PySpark, XGBoost, LangChain, FastAPI...
```

راجع `README.md` لخطوات التثبيت الكاملة على Windows/Linux/macOS.

---

*هذا المستند مرجع معماري عام. للتفاصيل الدقيقة (أسماء الأعمدة، الرسائل، الـ Endpoints) ارجع دائمًا لـ `data_contract.md`.*