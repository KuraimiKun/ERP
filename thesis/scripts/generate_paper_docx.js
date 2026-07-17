// Generates paper_sparsity.docx from the LaTeX source paper_sparsity.tex,
// reproducing the IEEEtran conference layout (two-column, Times New Roman).
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
  AlignmentType, LevelFormat, BorderStyle, WidthType, ShadingType,
  SectionType, TabStopType, TabStopPosition, HeadingLevel,
} = require(path.join(process.env.APPDATA, "npm", "node_modules", "docx"));

const FIG_DIR = path.join(__dirname, "..", "figures");
const OUT = path.join(__dirname, "..", "paper_sparsity.docx");

// ---------------------------------------------------------------- helpers
const TNR = "Times New Roman";
const BODY = 20;   // 10pt
const SMALL = 18;  // 9pt

const T = (text, opts = {}) => new TextRun({ text, font: TNR, size: BODY, ...opts });
const IT = (text, opts = {}) => T(text, { italics: true, ...opts });
const TT = (text, opts = {}) => new TextRun({ text, font: "Courier New", size: opts.size || BODY, ...opts });
// math variable with subscript, e.g. n_t
const nT = (opts = {}) => [IT("n", opts), IT("t", { subScript: true, ...opts })];

const P = (children, opts = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: 288 },
  children,
  ...opts,
});
const Pnoind = (children, opts = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  children,
  ...opts,
});

const sectionHead = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  alignment: AlignmentType.CENTER,
  spacing: { before: 220, after: 120 },
  children: [new TextRun({ text, font: TNR, size: BODY, smallCaps: true })],
});
const subHead = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  alignment: AlignmentType.LEFT,
  spacing: { before: 180, after: 100 },
  children: [new TextRun({ text, font: TNR, size: BODY, italics: true })],
});
// inline paragraph head like \paragraph*{Contributions.}
const parHead = (text) => IT(text, { bold: true });

const caption = (runs) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 80, after: 160 },
  children: runs.map(r => { r.root; return r; }),
});

const figure = (file, widthPx, heightPx, altTitle) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 160, after: 40 },
  children: [new ImageRun({
    type: "png",
    data: fs.readFileSync(path.join(FIG_DIR, file)),
    transformation: { width: widthPx, height: heightPx },
    altText: { title: altTitle, description: altTitle, name: altTitle },
  })],
});

// ---------------------------------------------------------------- title block
const titleBlock = [
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 120 },
    children: [
      new TextRun({ text: "Hallucinated Explanations in Multi-Tenant ERP Cold-Start Regimes:", font: TNR, size: 44 }),
      new TextRun({ text: "Empirical Evidence and a Maturity-Aware AI Routing Pattern", font: TNR, size: 44, break: 1 }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 40 },
    children: [new TextRun({ text: "Ahmed Ameen Hassan Alkuraimi", font: TNR, size: 22 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 0 },
    children: [
      T("Faculty of Engineering"),
      T("State University of Malang, Indonesia", { break: 1 }),
      TT("ahmed.ameen.2205356@students.um.ac.id", { break: 1 }),
    ],
  }),
  new Paragraph({ children: [] }),
];

// ---------------------------------------------------------------- abstract
const A = (text, opts = {}) => T(text, { bold: true, size: SMALL, ...opts });
const AI = (text, opts = {}) => A(text, { italics: true, ...opts });
const AnT = () => [AI("n"), AI("t", { subScript: true })];

const abstract = [
  Pnoind([
    AI("Abstract"), A("—Multi-tenant Software-as-a-Service Enterprise Resource Planning (ERP) platforms increasingly embed predictive models augmented with post-hoc Explainable AI (XAI) tools such as SHAP and LIME. We document a systems-level failure mode in this design: for cold-start tenants with only tens or hundreds of historical rows, SHAP and LIME continue to emit confident, well-formatted explanations even when the underlying classifier is statistically equivalent to random guessing. Using a controlled sparsity experiment over five simulated tenants (50,000, 5,000, 1,000, 200, 50 rows) on the Brazilian Olist e-commerce corpus, operationalised as a Late Delivery Risk task as a structural proxy for ERP-style operational-risk prediction (and explicitly generalising to the studied platform’s late-payment module), and trained under a strict order-time leakage-avoidance regime, we show that classical predictive metrics fail to track the regime change (AUC-ROC ∈ {0.66, 0.62, 0.61, 0.61, 0.89}, the last being a small-sample artefact), whereas baseline rank agreement of SHAP global importances against the data-rich reference tenant degrades near-monotonically (ρ = 1.000, 0.857, 0.643, 0.615, 0.449), crossing the conventional ρ ≥ 0.70 reliability threshold at exactly "),
    ...AnT(),
    A(" = 1,000 rows. Concurrently, absolute-SHAP variance explodes by more than two orders of magnitude (0.022 → 5.04), the empirical signature of a single feature absorbing the explanation mass. The qualitative cliff is replicated on the IBM HR Analytics Employee Attrition corpus and a synthetic CRM Lead Scoring corpus. We then propose and implement "),
    AI("Maturity-Aware AI Routing"),
    A(": a tier-logic gate ("),
    new TextRun({ text: "predict_or_heuristic", font: "Courier New", size: SMALL, bold: true }),
    A(") that, when "),
    ...AnT(),
    A(" ≤ 1,000, suppresses per-tenant local SHAP/LIME explanations and returns a serialised cross-tenant global heuristic derived from the data-rich reference. The pattern is additive, rollback-safe, and provides an auditable systems-level control consistent with emerging AI-accountability regulation. The empirical reliability cliff appears to be the first quantitative characterisation, in an ERP multi-tenant setting, of post-hoc XAI failure as a function of tenant data volume."),
  ], { spacing: { after: 120 } }),
  Pnoind([
    AI("Index Terms"),
    A("—Explainable AI, SHAP, LIME, multi-tenant SaaS, ERP, cold-start, data sparsity, reliability cliff, Maturity-Aware AI Routing."),
  ], { spacing: { after: 160 } }),
];

// ---------------------------------------------------------------- body
const intro = [
  sectionHead("I.  Introduction"),
  Pnoind([
    T("Cloud-hosted multi-tenant ERP systems have become a routine substrate on which Small and Medium-sized Enterprises (SMEs) consume embedded predictive services—late-payment risk, lead scoring, employee attrition, inventory forecasting—through a per-tenant data isolation model. The dominant interpretability stack pairs gradient-boosted trees with post-hoc XAI tools, most commonly SHAP [1], [2] and LIME [3], on the assumption that local attributions produced for individual records can be safely surfaced to non-technical end users."),
  ]),
  P([
    T("This assumption is well-supported in the data-rich enterprise regime, but not in the cold-start regime that characterises the long tail of SaaS ERP adoption. New tenants typically begin with tens to a few hundred invoices, employees, or leads, and the per-tenant inference path of a shared model can be invoked at "),
    ...nT(),
    T(" as low as a single-digit count. We show empirically that, in this regime, SHAP and LIME do not fail gracefully: they continue to emit attributions whose magnitudes, ranks, and natural-language framings are indistinguishable in form from those served to data-rich tenants, even when the model’s classifier behaviour has collapsed to near-random. We call this failure mode "),
    IT("hallucinated explanations"),
    T(", by analogy with hallucinated text in generative models: structurally plausible output, epistemically empty."),
  ]),
  Pnoind([parHead("Contributions."), T(" This paper makes three contributions:")], { spacing: { before: 100, after: 60 } }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "contrib", level: 0 },
    spacing: { after: 60 },
    children: [
      T("Empirical.", { bold: true }),
      T(" A controlled five-tier sparsity simulation ("),
      ...nT(),
      T(" ∈ {50,000, 5,000, 1,000, 200, 50}) on an ERP-style operational-risk task under a strict leakage-avoidance regime, showing that AUC-ROC is uninformative about XAI reliability and that baseline rank agreement of SHAP global importances crosses below ρ = 0.70 at "),
      ...nT(),
      T(" = 1,000, accompanied by a ~225× inflation of absolute-SHAP variance at "),
      ...nT(),
      T(" = 50. The cliff is replicated qualitatively on two additional ERP-native tasks."),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "contrib", level: 0 },
    spacing: { after: 60 },
    children: [
      T("Conceptual.", { bold: true }),
      T(" A reframing of post-hoc XAI evaluation in multi-tenant systems as a sparsity-conditioned reliability question rather than a per-record fidelity question, together with the explicit caveat that small-"),
      ...nT(),
      T(" Spearman against a reference tenant is a baseline rank agreement (not ground-truth fidelity)."),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "contrib", level: 0 },
    spacing: { after: 120 },
    children: [
      T("Architectural.", { bold: true }),
      T(" "),
      IT("Maturity-Aware AI Routing"),
      T(", a rollback-safe, additive software pattern implemented in a Django 4.2 multi-tenant ERP. A single threshold constant, τ = 1,000, governs a tier-logic gate that returns a pre-computed global heuristic instead of local SHAP/LIME for cold-start tenants."),
    ],
  }),
];

const related = [
  sectionHead("II.  Related Work"),
  subHead("A. Post-hoc Explainability"),
  Pnoind([
    T("SHAP [1] provides game-theoretic attributions with desirable axiomatic properties (efficiency, symmetry, dummy, additivity), and TreeSHAP [2] makes them tractable for the gradient-boosted trees that dominate tabular ERP modelling. LIME’s local surrogate models [3] are widely used as a complementary, model-agnostic explanation. Both tools are sample-based: their reliability depends on having enough training instances around the record of interest. Where this assumption fails, the literature has warned of stability and faithfulness issues [4], [5], but published guidance has remained largely qualitative, without per-tenant operating thresholds."),
  ]),
  subHead("B. Multi-Tenant SaaS ML"),
  Pnoind([
    T("The systems literature on multi-tenant SaaS [6], [7] has emphasised resource isolation and schema-versus-row tenancy trade-offs. ERP-specific deployments [8] layer business processes on top, and recent industry analyses [9], [10] document the embedding of ML modules into mainstream ERPs. The combination—a shared model serving heterogeneous tenants of vastly different data volumes, each receiving local XAI—has not, to our knowledge, been empirically audited for cold-start XAI reliability."),
  ]),
  subHead("C. AI Accountability and Documentation"),
  Pnoind([
    T("Model Cards [11] and Datasheets for Datasets [12] address documentation of model provenance and intended use. The EU AI Act [13] imposes operational constraints on automated decisions in some ERP-adjacent contexts. Our architectural contribution is consistent with these trajectories: the cold-start gate produces an auditable response payload explicitly stating the mode ("),
    IT("local"),
    T(" vs "),
    IT("global heuristic"),
    T("), the threshold, and the tenant volume, allowing downstream auditors to distinguish a per-tenant prediction from a fallback."),
  ]),
];

const problem = [
  sectionHead("III.  Problem Formulation"),
  Pnoind([
    T("Let "), IT("𝒯"), T(" = {"), IT("t"), T("₁, …, "), IT("t"), IT("m", { subScript: true }),
    T("} denote tenants of a multi-tenant ERP, each with historical record count "),
    ...nT(),
    T(". A shared family of models "), IT("f"), IT("t", { subScript: true }),
    T(" : 𝒳 → [0,1] produces tenant-specific risk estimates; a per-tenant explainer "),
    IT("g"), IT("t", { subScript: true }),
    T(" : 𝒳 → ℝ"), T("d", { superScript: true, italics: true }),
    T(" returns local attributions over "), IT("d"), T(" features."),
  ]),
  P([
    T("We assume a strict leakage-avoidance feature regime: only observables available "),
    IT("at order time"),
    T(" are admitted into 𝒳. For the primary Late Delivery Risk task on Olist, this excludes any post-shipment quantities (review timestamps, freight realisations, delivery deltas), and admits only order-time observables (freight pricing, item count, payment type, estimated delivery days, approval delay, purchase hour)."),
  ]),
  P([T("We define three sparsity-conditioned reliability metrics for the explanation system:")], { spacing: { after: 60 } }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [
      T("Baseline rank agreement", { bold: true }),
      T(" ρ"), IT("t", { subScript: true }),
      T(" = Spearman(φ"), IT("t", { subScript: true }),
      T(", φ"), IT("t*", { subScript: true }),
      T("), where φ"), IT("t", { subScript: true }),
      T(" is the global mean-absolute-SHAP feature-importance vector of tenant "), IT("t"),
      T(" and "), IT("t*"),
      T(" is the data-rich reference tenant. This is not a ground-truth fidelity claim; it is a reference-aligned explanation-stability measure."),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [
      T("Absolute-SHAP variance", { bold: true }),
      T(" σ²"), IT("t", { subScript: true }),
      T(" = Var(|φ"), IT("t", { subScript: true }),
      T("|), a concentration index for the explanation mass."),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 100 },
    children: [
      T("LIME top-", { bold: true }), IT("k", { bold: true }), T(" Jaccard stability", { bold: true }),
      T(" across resampled explanations of the same record, "), IT("k"), T(" = 5."),
    ],
  }),
  Pnoind([
    T("The architectural question is whether there exists a tenant-size threshold τ below which these metrics jointly indicate that per-tenant local explanations should be suppressed in favour of a global fallback."),
  ]),
];

const method = [
  sectionHead("IV.  Methodology"),
  subHead("A. Datasets and Tiering"),
  Pnoind([
    T("The primary study uses the Brazilian Olist e-commerce corpus (~99,000 orders). The binary target is"),
  ]),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 80 },
    children: [
      IT("y"), T(" = "), T("1", { bold: true }), T("["),
      IT("delivered_customer_date"), T(" > "), IT("estimated_delivery_date"), T("],"),
    ],
  }),
  Pnoind([
    T("operationalised as a structural proxy for ERP-style operational-risk prediction and explicitly generalised to the studied platform’s late-payment module (the systems gate, the global-heuristic artefact, and the response schema are identical in either substrate)."),
  ]),
  P([
    T("Five tenant tiers are simulated by stratified down-sampling: "),
    T("A", { bold: true }), T(" ("), IT("n"), T(" = 50,000, reference), "),
    T("B", { bold: true }), T(" (5,000), "),
    T("C", { bold: true }), T(" (1,000), "),
    T("D", { bold: true }), T(" (200), "),
    T("E", { bold: true }), T(" (50). Class prevalence and the global hold-out evaluation set are held constant across tiers, isolating data volume as the manipulated variable."),
  ]),
  subHead("B. Cross-Task Replication"),
  Pnoind([
    T("To probe external validity, the same pipeline (down-sampling protocol, leakage screen, evaluation harness) is re-run on: (i) "),
    T("IBM HR Analytics Employee Attrition", { bold: true }),
    T(" ("), IT("n"), T(" = 1,470, public), on tiers 1,470 / 500 / 200 / 50, and (ii) "),
    T("Synthetic CRM Lead Scoring", { bold: true }),
    T(" ("), IT("n"), T(" = 5,000, generated; 34 features post-encoding, 21.3% prevalence; conversion timestamps and PII removed pre-encoding as leakage controls)."),
  ]),
  subHead("C. Models and Explainers"),
  Pnoind([
    T("For the primary study and HR Attrition, the classifier is a "),
    TT("GradientBoostingClassifier"),
    T(" (scikit-learn) with default hyperparameters; for CRM Lead Scoring, a tuned configuration ("),
    TT("n_estimators"), T(" = 200, "), TT("max_depth"), T(" = 3, "), TT("learning_rate"), T(" = 0.05) chosen on the data-rich tier. Explanations are computed with TreeExplainer (SHAP) for global rank correlation and variance, and "),
    TT("LimeTabular"),
    T(" for top-"), IT("k"), T(" Jaccard."),
  ]),
  subHead("D. Routing Architecture"),
  Pnoind([T("The routing rule is")]),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 80, after: 0 },
    tabStops: [{ type: TabStopType.RIGHT, position: 4860 }],
    children: [
      T("explain("), IT("t"), T(", "), IT("x"), T(") = "),
      TT("GlobalHeuristic"), T("(),"),
      T("   if "), ...nT(), T(" ≤ τ,"),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 80 },
    tabStops: [{ type: TabStopType.RIGHT, position: 4860 }],
    children: [
      T("explain("), IT("t"), T(", "), IT("x"), T(") = "),
      TT("LocalShapLime"), T("("), IT("t"), T(", "), IT("x"), T("),"),
      T("   otherwise,"),
      T("\t(1)"),
    ],
  }),
  Pnoind([
    T("with τ = 1,000 (Fig. 1). Under the inclusive boundary, the equivalent code-side constant in the Django implementation is "),
    TT("MIN_LOCAL_EXPLANATION_RECORDS"),
    T(" = 1,001."),
  ]),
  figure("sparsity_fig_3_2_routing_architecture.png", 312, 189, "Maturity-Aware AI Routing gate"),
  caption([
    T("Fig. 1.  Maturity-Aware AI Routing gate. Inclusive boundary ", { size: SMALL }),
    IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true }),
    T(" ≤ 1,000; equivalent code-side form ", { size: SMALL }),
    IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true }),
    T(" < ", { size: SMALL }),
    new TextRun({ text: "MIN_LOCAL_EXPLANATION_RECORDS", font: "Courier New", size: 16 }),
    T(" (= 1,001).", { size: SMALL }),
  ]),
  Pnoind([
    T("The cold branch reads a pre-computed JSON artefact, abbreviated below to the leading entry:"),
  ], { spacing: { after: 80 } }),
  new Table({
    width: { size: 4860, type: WidthType.DXA },
    columnWidths: [4860],
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: 4860, type: WidthType.DXA },
        borders: {
          top: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
          bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
          left: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
          right: { style: BorderStyle.SINGLE, size: 4, color: "000000" },
        },
        margins: { top: 60, bottom: 60, left: 100, right: 100 },
        children: [
          "{",
          "  \"mode\": \"global_heuristic\",",
          "  \"threshold\": 1000,",
          "  \"baseline_tenant\": \"A\",",
          "  \"baseline_n\": 50000,",
          "  \"top_features\": [",
          "    {\"feature\": \"freight_value\",",
          "     \"importance\": 0.30, \"rank\": 1}",
          "    // ... 4 more entries ...",
          "  ],",
          "  \"reason\": \"Tenant data volume below the",
          "   empirically-determined reliability threshold;",
          "   serving global cross-tenant feature importance.\"",
          "}",
        ].map(line => new Paragraph({
          spacing: { after: 0, line: 200, lineRule: "auto" },
          children: [new TextRun({ text: line, font: "Courier New", size: 14 })],
        })),
      })],
    })],
  }),
  new Paragraph({ children: [], spacing: { after: 80 } }),
];

// ----------------------------------------------- results (table + cliff fig)
const thinTop = { style: BorderStyle.SINGLE, size: 8, color: "000000" };
const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const tCell = (runs, { header = false, align = AlignmentType.RIGHT, borders = {} } = {}, w) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: { top: none, bottom: none, left: none, right: none, ...borders },
    margins: { top: 30, bottom: 30, left: 60, right: 60 },
    children: [new Paragraph({ alignment: align, children: runs })],
  });

const colW = [640, 940, 1020, 680, 820, 760];
const tableRows = [
  // header
  new TableRow({
    children: [
      tCell([T("Tenant", { size: SMALL })], { align: AlignmentType.LEFT, borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[0]),
      tCell([IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true })], { borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[1]),
      tCell([T("AUC-ROC", { size: SMALL })], { borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[2]),
      tCell([T("F1", { size: SMALL })], { borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[3]),
      tCell([T("ρ", { size: SMALL, italics: true })], { borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[4]),
      tCell([T("σ²(|φ|)", { size: SMALL, italics: true })], { borders: { top: thinTop, bottom: { style: BorderStyle.SINGLE, size: 4, color: "000000" } } }, colW[5]),
    ],
  }),
  ...[
    ["A", "50,000", "0.6556", "0.0263", "1.0000", "0.0224"],
    ["B", "5,000", "0.6249", "0.1136", "0.8571", "0.0245"],
    ["C", "1,000", "0.6094", "0.0500", "0.6429", "0.0510"],
    ["D", "200", "0.6126", "0.0000", "0.6154", "0.2017"],
    ["E", "50", "0.8889", "0.0000", "0.4485", "5.0392"],
  ].map((row, i, arr) => new TableRow({
    children: row.map((v, j) => tCell(
      [T(v, { size: SMALL })],
      { align: j === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
        borders: i === arr.length - 1 ? { bottom: thinTop } : {} },
      colW[j]
    )),
  })),
];

const results = [
  sectionHead("V.  Results"),
  subHead("A. Predictive Metrics are Uninformative"),
  Pnoind([
    T("Table I reports leakage-corrected AUC-ROC, F1, and the three reliability metrics for the primary study. AUC-ROC is essentially flat across A–D (0.66, 0.62, 0.61, 0.61) and "),
    IT("rises"),
    T(" to 0.89 at the extreme cold-start tier E—a well-understood small-sample artefact in which a single concentrated feature happens to discriminate on the small hold-out subset. Any monitoring stack that relies on AUC-ROC would therefore conclude that the cold-start tier is the "),
    IT("healthiest"),
    T(" of the five, while the explanation system is, in fact, at its most degraded."),
  ]),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 160, after: 40 },
    children: [T("TABLE I", { size: SMALL, smallCaps: true })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 80 },
    children: [
      T("Primary study (Olist Late Delivery Risk, leakage-free regime): predictive metrics are flat or misleading while explanation-system metrics collapse as ", { size: SMALL, smallCaps: true }),
      IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true }),
      T(" falls.", { size: SMALL, smallCaps: true }),
    ],
  }),
  new Table({
    alignment: AlignmentType.CENTER,
    width: { size: 4860, type: WidthType.DXA },
    columnWidths: colW,
    rows: tableRows,
  }),
  new Paragraph({ children: [], spacing: { after: 120 } }),
  subHead("B. The Reliability Cliff"),
  Pnoind([
    T("Baseline rank agreement ρ against the Tenant A reference traces a near-monotonic descent: 1.0000 → 0.8571 → 0.6429 → 0.6154 → 0.4485. The conventional reliability bound ρ ≥ 0.70 is crossed for the first time at Tenant C—exactly at "),
    ...nT(),
    T(" = 1,000 (Fig. 2). This is the empirical anchor for the threshold in Eq. (1)."),
  ]),
  figure("sparsity_fig_4_2_reliability_cliff.png", 312, 171, "Reliability cliff"),
  caption([
    T("Fig. 2.  Reliability cliff. Baseline rank agreement of SHAP global importances against Tenant A vs log", { size: SMALL }),
    T("10", { size: SMALL, subScript: true }),
    T(" ", { size: SMALL }),
    IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true }),
    T(". The horizontal dashed line marks the conventional ρ = 0.70 bound; the vertical dashed line marks the empirical crossing at ", { size: SMALL }),
    IT("n", { size: SMALL }), IT("t", { size: SMALL, subScript: true }),
    T(" = 1,000.", { size: SMALL }),
  ]),
  Pnoind([
    parHead("An anti-pattern caveat."),
    T(" Below τ, the effective feature support also collapses (Tenant D’s mass concentrates on two features; Tenant E’s on a single feature). When the ranking domain collapses, ρ against the reference becomes a Spearman of a degenerate ranking, and residual orderings can "),
    IT("accidentally"),
    T(" agree with the data-rich top-of-list by chance, producing transient apparent recoveries that are not restored fidelity. The mild C–D plateau in Table I is the benign form of this effect; a hypothetical rebound "),
    IT("above"),
    T(" 0.70 at very small "),
    ...nT(),
    T(" would be a small-sample-variance artefact that would "),
    IT("reinforce"),
    T(", not undermine, the case for an architectural gate—the explanation surface in that regime is no longer a well-defined statistical object. This is why the gate keys on tenant data volume, an observable architectural quantity, rather than on a runtime estimate of ρ itself."),
  ], { spacing: { before: 100 } }),
  subHead("C. Explanation Volatility Explodes"),
  Pnoind([
    T("Absolute-SHAP variance is well-behaved at the data-rich tiers (0.0224, 0.0245), grows modestly at the threshold (0.0510 at C), and then explodes by an order of magnitude at D (0.2017) and by more than two orders of magnitude at E (5.0392, i.e. ~225× the Tenant A baseline). Inspection of the underlying attributions shows the mechanism: at E, a single feature ("),
    TT("estimated_delivery_days"),
    T(") carries an attribution of 4.77, while the second feature collapses to 0.19. This is what we call the “grasping at straws” effect—explanation mass concentrated on whichever feature happened to discriminate on the few available training rows, surfaced to the end user as a confident SHAP plot."),
  ]),
  subHead("D. Cross-Task Replication"),
  Pnoind([
    T("On the IBM HR Attrition corpus the same qualitative pattern recurs: AUC-ROC is near chance on the smaller tiers while ρ against the data-rich reference deteriorates and absolute-SHAP variance grows. On the synthetic CRM Lead Scoring corpus the data-rich reference reaches AUC-ROC = 0.719 and the cold-start sub-tiers reproduce both characteristic symptoms (rank-correlation decay and variance inflation). The pattern is therefore not a peculiarity of the Olist substrate; it is the expected behaviour of sample-based post-hoc XAI under a shared-model multi-tenant deployment with vastly heterogeneous "),
    ...nT(),
    T("."),
  ]),
];

const arch = [
  sectionHead("VI.  Architectural Pattern: Maturity-Aware AI Routing"),
  Pnoind([
    T("The routing rule of Eq. (1) is implemented as a single public method on the platform’s predictor service, "),
    TT("predict_or_heuristic(invoice)"),
    T(" (the Django class is named "),
    TT("LatePaymentPredictor"),
    T("; the same class is reused, unchanged, for the Late Delivery Risk experiment). The method inspects "),
    TT("_invoice_count()"),
    T(" and dispatches to one of two private branches:"),
  ], { spacing: { after: 60 } }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 60 },
    children: [
      TT("_load_global_heuristic()"),
      T("—a memoised loader that reads the cross-tenant SHAP feature-importance artefact "),
      TT("cold_start_heuristic.json"),
      T(" from disk and returns it as a structured explanation payload;"),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 100 },
    children: [
      TT("predict()"),
      T("—the existing per-tenant ML inference and SHAP/LIME explanation routine, left fully unchanged."),
    ],
  }),
  Pnoind([
    T("The two branches conform to a single response schema—{"),
    IT("mode"), T(", "), IT("threshold"), T(", "), IT("count"), T(", "), IT("explanation"),
    T("}—so downstream consumers can be agnostic to which branch executed while still being able to surface the routing decision ("),
    IT("mode"),
    T(") to the end user. The artefact itself is generated once offline at the end of the sparsity experiment (top-"),
    IT("k"), T(", "), IT("k"),
    T(" = 5 from the Tenant A global mean-absolute-SHAP vector, plus the tenant size, prevalence and a short human-readable reason string), serialised to JSON, and versioned alongside the trained models. At runtime the artefact is cached after first read so cold-start prediction incurs no per-request I/O."),
  ]),
  P([
    T("The pattern is intentionally "),
    IT("additive"),
    T(": it can be enabled by switching call sites from "),
    TT("predict()"),
    T(" to "),
    TT("predict_or_heuristic()"),
    T(", and rolled back by reversing the same switch, without any database migration or downtime. This is what makes the gate deployable as a systems-level control in production multi-tenant ERPs."),
  ]),
];

const threats = [
  sectionHead("VII.  Threats to Validity"),
  Pnoind([
    parHead("Construct validity."),
    T(" The Late Delivery Risk target is not identical to late payment in a financial sense; it is used here as a structural proxy for ERP-style operational-risk prediction. The architectural gate, the global-heuristic artefact, and the response schema are unchanged between the two substrates. We therefore claim external validity for the architectural pattern, not for the specific empirical numbers in Table I."),
  ], { spacing: { after: 100 } }),
  Pnoind([
    parHead("Internal validity."),
    T(" Tenants are simulated by stratified down-sampling rather than drawn from distinct organisations. Class prevalence and the hold-out evaluation set are held constant across tiers to isolate "),
    ...nT(),
    T(" as the manipulated variable. The reported AUC-ROC, F1, ρ and σ² values are obtained under a strict order-time leakage screen; introducing post-shipment features inflates AUC-ROC to > 0.99 on the same task, masking the cliff."),
  ], { spacing: { after: 100 } }),
  Pnoind([
    parHead("Reference-aligned, not ground-truth."),
    T(" ρ against Tenant A is a baseline rank agreement, not a ground-truth fidelity claim. Tenant A itself has AUC-ROC = 0.6556 and F1 = 0.0263 under the leakage-free regime, and its SHAP ranking is therefore the most data-supported reference available within the experiment, not a gold standard."),
  ], { spacing: { after: 100 } }),
  Pnoind([
    parHead("External validity."),
    T(" Replication on HR Attrition and CRM Lead Scoring supports the architectural finding qualitatively. A multi-organisation field study (multiple real tenants of the same deployed ERP, varying naturally in "),
    ...nT(),
    T(") would be the natural next step."),
  ]),
];

const conclusion = [
  sectionHead("VIII.  Conclusion"),
  Pnoind([
    T("We have shown that, in a multi-tenant ERP setting with strict leakage-avoidance, post-hoc SHAP and LIME explanations exhibit a reliability cliff at "),
    ...nT(),
    T(" = 1,000 that classical predictive metrics do not detect, and that the cliff is accompanied by an order-of-magnitude inflation of absolute-SHAP variance as the explanation mass collapses onto a small number of features. The cliff replicates qualitatively on two further ERP-native tasks. To convert the empirical finding into a deployable control, we proposed and implemented "),
    IT("Maturity-Aware AI Routing"),
    T(": a single tier-logic gate whose threshold is grounded in the empirical crossing and whose cold branch returns an auditable, versioned global heuristic instead of a hallucinated local explanation. The pattern is additive and rollback-safe, and is, we argue, the kind of systems-level control that emerging AI-accountability regulation will require operators of multi-tenant predictive ERP services to provide."),
  ]),
];

const acks = [
  sectionHead("Acknowledgements"),
  Pnoind([
    T("The author thanks the supervisor, Dr. Eng. Muhammad Ashar, S.T., M.T., for guidance throughout the underlying bachelor-thesis project at the State University of Malang."),
  ]),
];

// ---------------------------------------------------------------- references
const refs = [
  ["S. M. Lundberg and S.-I. Lee, “A unified approach to interpreting model predictions,” ", "Advances in Neural Information Processing Systems", ", vol. 30, 2017."],
  ["S. M. Lundberg, G. Erion, H. Chen, A. DeGrave, J. M. Prutkin, B. Nair, R. Katz, J. Himmelfarb, N. Bansal, and S.-I. Lee, “From local explanations to global understanding with explainable AI for trees,” ", "Nature Machine Intelligence", ", vol. 2, no. 1, pp. 56–67, 2020."],
  ["M. T. Ribeiro, S. Singh, and C. Guestrin, “‘Why should I trust you?’: Explaining the predictions of any classifier,” in ", "Proc. of the 22nd ACM SIGKDD Int. Conf. on Knowledge Discovery and Data Mining", ", 2016, pp. 1135–1144."],
  ["Z. C. Lipton, “The mythos of model interpretability,” ", "Communications of the ACM", ", vol. 61, no. 10, pp. 36–43, 2018."],
  ["C. Rudin, “Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead,” ", "Nature Machine Intelligence", ", vol. 1, no. 5, pp. 206–215, 2019."],
  ["C.-P. Bezemer and A. Zaidman, “Multi-tenant SaaS applications: maintenance dream or nightmare?” ", "Proc. of the Joint ERCIM Workshop on Software Evolution and Int. Workshop on Principles of Software Evolution", ", pp. 88–92, 2010."],
  ["R. Krebs, C. Momm, and S. Kounev, “Architectural concerns in multi-tenant SaaS applications,” ", "Proc. of the 2nd Int. Conf. on Cloud Computing and Services Science", ", 2014."],
  ["M. Haddara and O. Zach, “ERP systems in SMEs: a literature review,” ", "Proc. of the 44th Hawaii Int. Conf. on System Sciences", ", 2011."],
  ["Gartner, “Magic quadrant for cloud ERP for service-centric enterprises,” Industry Report, 2023.", null, null],
  ["IDC, “Worldwide embedded AI in enterprise applications forecast,” Industry Report, 2024.", null, null],
  ["M. Mitchell, S. Wu, A. Zaldivar, P. Barnes, L. Vasserman, B. Hutchinson, E. Spitzer, I. D. Raji, and T. Gebru, “Model cards for model reporting,” in ", "Proc. of the Conference on Fairness, Accountability, and Transparency", ", 2019, pp. 220–229."],
  ["T. Gebru, J. Morgenstern, B. Vecchione, J. W. Vaughan, H. Wallach, H. Daumé III, and K. Crawford, “Datasheets for datasets,” ", "Communications of the ACM", ", vol. 64, no. 12, pp. 86–92, 2021."],
  ["European Commission, “Regulation of the European Parliament and of the Council laying down harmonised rules on artificial intelligence (AI Act),” Official Journal of the European Union, 2024.", null, null],
];

const references = [
  sectionHead("References"),
  ...refs.map(([pre, ital, post], i) => new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    indent: { left: 360, hanging: 360 },
    spacing: { after: 60 },
    children: [
      T(`[${i + 1}] `, { size: SMALL }),
      T(pre, { size: SMALL }),
      ...(ital ? [IT(ital, { size: SMALL }), T(post, { size: SMALL })] : []),
    ],
  })),
];

// ---------------------------------------------------------------- document
const doc = new Document({
  creator: "Ahmed Ameen Hassan Alkuraimi",
  title: "Hallucinated Explanations in Multi-Tenant ERP Cold-Start Regimes",
  styles: {
    default: { document: { run: { font: TNR, size: BODY } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: BODY, font: TNR, smallCaps: true, color: "000000", bold: false },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: BODY, font: TNR, italics: true, color: "000000", bold: false },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [
      { reference: "contrib",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1)", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 480, hanging: 300 } } } }] },
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 480, hanging: 300 } } } }] },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1080, bottom: 1440, left: 1080 },
        },
      },
      children: titleBlock,
    },
    {
      properties: {
        type: SectionType.CONTINUOUS,
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1080, right: 1080, bottom: 1440, left: 1080 },
        },
        column: { count: 2, space: 360, equalWidth: true },
      },
      children: [
        ...abstract, ...intro, ...related, ...problem, ...method,
        ...results, ...arch, ...threats, ...conclusion, ...acks, ...references,
      ],
    },
  ],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUT, buffer);
  console.log("Wrote", OUT, buffer.length, "bytes");
});
