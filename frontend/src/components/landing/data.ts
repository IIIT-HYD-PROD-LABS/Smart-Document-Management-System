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
    "Received": { bg: "bg-[#27272a]", text: "text-[#a1a1aa]" },
    "Under Review": { bg: "bg-amber-500/10", text: "text-amber-400" },
    "Response Drafted": { bg: "bg-blue-500/10", text: "text-blue-400" },
    "Submitted": { bg: "bg-purple-500/10", text: "text-purple-400" },
    "Resolved": { bg: "bg-emerald-500/10", text: "text-emerald-400" },
};

export const processSteps = [
    {
        number: "01",
        title: "Upload",
        description: "Upload notices from any source — PDF, scan, email forward, or direct portal fetch.",
    },
    {
        number: "02",
        title: "Classify",
        description: "AI classifies into 40+ notice types across GST, Income Tax, MCA, RBI, and SEBI.",
    },
    {
        number: "03",
        title: "Alert",
        description: "Tiered alerts at T-7, T-3, T-1 before every deadline. Email, SMS, and in-app.",
    },
    {
        number: "04",
        title: "Resolve",
        description: "Draft responses with AI assist, attach evidence, track through to resolution.",
    },
] as const;

export const stats = [
    { value: "78%", label: "of SMEs miss at least one filing deadline per year" },
    { value: "₹45K+", label: "average penalty per late GST return filing" },
    { value: "200+", label: "compliance checkpoints across 5 authorities" },
] as const;
