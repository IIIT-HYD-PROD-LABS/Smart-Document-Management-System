"use client";

import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
} from "recharts";

// Light-theme calibrated category palette, deeper saturations for AA on white.
const CATEGORY_COLORS: Record<string, string> = {
    bills:    "#047857",
    upi:      "#6d28d9",
    tickets:  "#b45309",
    tax:      "#1d4ed8",
    bank:     "#0e7490",
    invoices: "#be185d",
    unknown:  "#71717a",
};

const tooltipStyle = {
    backgroundColor: "var(--bg-elevated)",
    border: "1px solid var(--border-default)",
    borderRadius: "8px",
    color: "var(--text-primary)",
    fontSize: 12,
    boxShadow: "var(--shadow-md)",
};

export interface TrendDatum {
    month: string;
    count: number;
}

export interface CategoryDatum {
    name: string;
    value: number;
}

interface TrendsChartProps {
    data: TrendDatum[];
}

export default function TrendsChart({ data }: TrendsChartProps) {
    if (data.length === 0) {
        return (
            <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>
                No trend data available
            </p>
        );
    }

    return (
        <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <defs>
                    <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2563eb" stopOpacity={0.18} />
                        <stop offset="100%" stopColor="#2563eb" stopOpacity={0} />
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                <XAxis
                    dataKey="month"
                    tick={{ fill: "#71717a", fontSize: 12 }}
                    axisLine={{ stroke: "#e4e4e7" }}
                    tickLine={false}
                />
                <YAxis
                    allowDecimals={false}
                    tick={{ fill: "#71717a", fontSize: 12 }}
                    axisLine={{ stroke: "#e4e4e7" }}
                    tickLine={false}
                />
                <Tooltip
                    contentStyle={tooltipStyle}
                    labelStyle={{ color: "#52525b" }}
                    cursor={{ stroke: "#d4d4d8", strokeDasharray: "3 3" }}
                />
                <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#2563eb"
                    strokeWidth={2}
                    fill="url(#trendGradient)"
                    name="Uploads"
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}

export function CategoryDonut({ data }: { data: CategoryDatum[] }) {
    if (data.length === 0) {
        return <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>No data</p>;
    }

    return (
        <div className="flex flex-col items-center">
            <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                    <Pie
                        data={data}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        dataKey="value"
                        paddingAngle={2}
                    >
                        {data.map((entry) => (
                            <Cell
                                key={entry.name}
                                fill={CATEGORY_COLORS[entry.name] ?? "#71717a"}
                                stroke="#ffffff"
                                strokeWidth={2}
                            />
                        ))}
                    </Pie>
                    <Tooltip
                        contentStyle={tooltipStyle}
                        formatter={(value: number, name: string) => [value, name]}
                    />
                </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
                {data.map((entry) => (
                    <div key={entry.name} className="flex items-center gap-1.5">
                        <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: CATEGORY_COLORS[entry.name] ?? "#71717a" }}
                        />
                        <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>{entry.name}</span>
                        <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>{entry.value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}
