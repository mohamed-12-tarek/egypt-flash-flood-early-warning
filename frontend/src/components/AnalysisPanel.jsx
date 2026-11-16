export default function AnalysisPanel({ lang }) {
  const isArabic = lang === "ar";

  return (
    <section className="card analysis-placeholder">
      <p className="eyebrow">
        {isArabic ? "قسم التحليلات" : "Analytics"}
      </p>

      <p>
        {isArabic
          ? "معلّق مؤقتًا — نرجعله بعد استلام مواصفات API التحليل."
          : "Coming soon — revisit after the analysis API is documented."}
      </p>

      {/* TODO: Connect the analysis API after its contract is confirmed. */}
    </section>
  );
}