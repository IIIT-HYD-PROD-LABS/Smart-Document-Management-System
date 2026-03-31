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

export const processSteps = [
    {
        number: "01",
        title: "Upload",
        description:
            "Upload any document or compliance notice \u2014 PDF, scan, email forward, or portal fetch.",
    },
    {
        number: "02",
        title: "Classify",
        description:
            "AI classifies into 50+ document types and 40+ compliance notice types across GST, IT, MCA, RBI, SEBI.",
    },
    {
        number: "03",
        title: "Extract & Track",
        description:
            "Smart extraction of dates, amounts, deadlines. Auto-track compliance timelines with risk scoring.",
    },
    {
        number: "04",
        title: "Act",
        description:
            "Search documents instantly, get deadline alerts, draft responses with AI assist, full audit trail.",
    },
] as const;

export const stats = [
    { value: "78%", label: "of SMEs miss at least one filing deadline per year" },
    { value: "\u20B945K+", label: "average penalty per late GST return filing" },
    { value: "40hrs", label: "spent monthly on manual document sorting per team" },
    { value: "97%", label: "classification accuracy across 50+ document types" },
] as const;
