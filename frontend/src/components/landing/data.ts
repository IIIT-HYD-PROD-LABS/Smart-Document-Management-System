// ---------------------------------------------------------------------------
// TaxSync Landing Page — Data
// ---------------------------------------------------------------------------

// Pain points: specific, role-based problems (not generic)
export const painPoints = [
    {
        title: "The Filing Clerk Bottleneck",
        description:
            "Every invoice, contract, and tax form lands in the same inbox. A junior associate spends 40+ hours a month renaming, tagging, and filing documents by hand — and still misfiled items surface during audits.",
    },
    {
        title: "The Missed-Deadline Spiral",
        description:
            "A GST mismatch notice arrives on a Friday. It sits in someone's inbox over the weekend. By Monday the 7-day window is half gone, the CA hasn't seen it, and a penalty is already accruing interest.",
    },
    {
        title: "The Multi-Entity Nightmare",
        description:
            "CAs juggling 15 clients across different GSTINs and PANs track deadlines in spreadsheets. One wrong filter and a client's FEMA declaration slips through. The first they hear of it is a show-cause notice.",
    },
    {
        title: "The Audit-Eve Scramble",
        description:
            "Assessment year closes and the team starts hunting for invoices across email, Google Drive, and WhatsApp. Version confusion means the wrong ITR draft gets submitted. Rectification adds weeks.",
    },
] as const;

// Solution capabilities — Smart Document Management
export const docFeatures = [
    {
        title: "Auto-Classification",
        description:
            "Upload any document. ML classifies into 50+ types — invoices, contracts, tax returns, legal notices — with 97% accuracy.",
    },
    {
        title: "Smart Extraction",
        description:
            "AI extracts dates, amounts, vendor names, GSTIN, PAN from every document. No manual data entry.",
    },
    {
        title: "Full-Text Search",
        description:
            "Find any document instantly. Search across extracted text, metadata, amounts, dates. Fuzzy matching catches typos.",
    },
    {
        title: "Version Control",
        description:
            "Track every revision. Compare versions, rollback changes, complete audit trail of who changed what.",
    },
] as const;

// Solution capabilities — Compliance Notice Tracking
export const complianceFeatures = [
    {
        title: "Notice Tracking",
        description:
            "Track notices from GST, Income Tax, MCA, RBI, and SEBI. Status workflow from Received through Resolution.",
    },
    {
        title: "Risk Scoring",
        description:
            "Every notice auto-scored for risk (Critical/High/Medium/Low). SHAP explanations show why.",
    },
    {
        title: "Deadline Alerts",
        description:
            "Tiered reminders at T-7, T-3, T-1 days. Email, SMS, in-app. Escalation to Compliance Head and CFO.",
    },
    {
        title: "Multi-Entity Management",
        description:
            "CAs manage multiple clients with distinct GSTINs/PANs. Client-scoped dashboards with zero cross-client leakage.",
    },
] as const;

// Process steps — the end-to-end workflow
export const processSteps = [
    {
        number: "01",
        title: "Upload",
        description:
            "Drop any document or compliance notice. PDF, scan, DOCX, or email forward.",
    },
    {
        number: "02",
        title: "Classify",
        description:
            "ML classifies into 50+ document types and 40+ notice types across 5 authorities.",
    },
    {
        number: "03",
        title: "Extract",
        description:
            "AI pulls dates, amounts, deadlines, legal sections. Auto-tracks compliance timelines.",
    },
    {
        number: "04",
        title: "Act",
        description:
            "Search instantly. Get deadline alerts. Draft responses. Export audit-ready reports.",
    },
] as const;

// Stats banner
export const stats = [
    { value: "78%", label: "of SMEs miss at least one filing deadline per year" },
    { value: "\u20B945K+", label: "average penalty per late GST return filing" },
    { value: "40hrs", label: "spent monthly on manual document sorting per team" },
    { value: "97%", label: "classification accuracy across 50+ document types" },
] as const;

// Demo data — documents table
export const demoDocuments = [
    {
        date: "2026-03-29",
        name: "Q3 Invoice - TCS Ltd",
        category: "Invoice",
        confidence: 97,
        amount: "\u20B92,45,000",
        status: "Classified",
    },
    {
        date: "2026-03-27",
        name: "NDA - Sterling Partners",
        category: "Contract",
        confidence: 94,
        amount: "\u2014",
        status: "Classified",
    },
    {
        date: "2026-03-24",
        name: "ITR-3 FY 2025-26",
        category: "Tax Return",
        confidence: 91,
        amount: "\u20B98,92,340",
        status: "Processing",
    },
    {
        date: "2026-03-20",
        name: "Board Resolution - AGM",
        category: "Legal",
        confidence: 88,
        amount: "\u2014",
        status: "Classified",
    },
    {
        date: "2026-03-18",
        name: "GSTR-9 Annual Return",
        category: "GST Filing",
        confidence: 96,
        amount: "\u20B912,45,670",
        status: "Classified",
    },
] as const;

// Demo data — compliance notices table
export const demoNotices = [
    {
        date: "2026-03-28",
        authority: "GST",
        type: "GSTR-3B Mismatch",
        risk: "Critical",
        riskScore: 92,
        status: "Under Review",
        deadline: "2026-04-15",
        entity: "Acme Pvt Ltd",
    },
    {
        date: "2026-03-25",
        authority: "IT",
        type: "TDS Return Default",
        risk: "High",
        riskScore: 78,
        status: "Response Drafted",
        deadline: "2026-04-10",
        entity: "Globex Corp",
    },
    {
        date: "2026-03-22",
        authority: "MCA",
        type: "Annual Filing Delay",
        risk: "Medium",
        riskScore: 55,
        status: "Received",
        deadline: "2026-04-30",
        entity: "Acme Pvt Ltd",
    },
    {
        date: "2026-03-18",
        authority: "RBI",
        type: "FEMA Declaration",
        risk: "High",
        riskScore: 81,
        status: "Submitted",
        deadline: "2026-04-05",
        entity: "Sterling Exports",
    },
    {
        date: "2026-03-15",
        authority: "SEBI",
        type: "Disclosure Violation",
        risk: "Low",
        riskScore: 28,
        status: "Resolved",
        deadline: "2026-03-30",
        entity: "Globex Corp",
    },
] as const;

// ---------------------------------------------------------------------------
// Color maps for badges
// ---------------------------------------------------------------------------

export const categoryColors: Record<string, { bg: string; text: string }> = {
    Invoice: { bg: "bg-blue-500/10", text: "text-blue-400" },
    Contract: { bg: "bg-purple-500/10", text: "text-purple-400" },
    "Tax Return": { bg: "bg-amber-500/10", text: "text-amber-400" },
    Legal: { bg: "bg-pink-500/10", text: "text-pink-400" },
    "GST Filing": { bg: "bg-cyan-500/10", text: "text-cyan-400" },
};

export const authorityColors: Record<string, { bg: string; text: string }> = {
    GST: { bg: "bg-blue-500/10", text: "text-blue-400" },
    IT: { bg: "bg-amber-500/10", text: "text-amber-400" },
    MCA: { bg: "bg-purple-500/10", text: "text-purple-400" },
    RBI: { bg: "bg-cyan-500/10", text: "text-cyan-400" },
    SEBI: { bg: "bg-pink-500/10", text: "text-pink-400" },
};

export const riskColors: Record<string, { bg: string; text: string }> = {
    Critical: { bg: "bg-red-500/10", text: "text-red-400" },
    High: { bg: "bg-orange-500/10", text: "text-orange-400" },
    Medium: { bg: "bg-yellow-500/10", text: "text-yellow-400" },
    Low: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
};

export const statusColors: Record<string, { bg: string; text: string }> = {
    Received: { bg: "bg-[#27272a]", text: "text-[#a1a1aa]" },
    "Under Review": { bg: "bg-amber-500/10", text: "text-amber-400" },
    "Response Drafted": { bg: "bg-blue-500/10", text: "text-blue-400" },
    Submitted: { bg: "bg-purple-500/10", text: "text-purple-400" },
    Resolved: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
};

export const docStatusColors: Record<string, { bg: string; text: string }> = {
    Classified: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
    Processing: { bg: "bg-amber-500/10", text: "text-amber-400" },
};

export function getConfidenceColor(score: number): { bg: string; text: string } {
    if (score >= 90) return { bg: "bg-emerald-500/10", text: "text-emerald-400" };
    if (score >= 75) return { bg: "bg-amber-500/10", text: "text-amber-400" };
    return { bg: "bg-red-500/10", text: "text-red-400" };
}

// ---------------------------------------------------------------------------
// Testimonial
// ---------------------------------------------------------------------------

export const testimonial = {
    quote: "We were tracking compliance in spreadsheets and praying nothing slipped through. Last year we missed an MCA filing and the penalty wiped out an entire month of margins. Never again.",
    author: "Priya Sharma",
    role: "CFO, Mid-size Manufacturing Firm",
    initials: "PS",
} as const;
