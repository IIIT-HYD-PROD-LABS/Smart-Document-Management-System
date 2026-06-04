"use client";

import React, { useEffect, useState } from "react";
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
// Each key maps to [light, dark] so the donut tracks the active theme.
const CATEGORY_COLORS: Record<string, [string, string]> = {
    bills:    ["#047857", "#10b981"],
    upi:      ["#6d28d9", "#a78bfa"],
    tickets:  ["#b45309", "#f59e0b"],
    tax:      ["#1d4ed8", "#60a5fa"],
    bank:     ["#0e7490", "#06b6d4"],
    invoices: ["#be185d", "#f472b6"],
    unknown:  ["#71717a", "#a1a1aa"],
};

// recharts needs concrete color strings (not var()), so resolve the design
// tokens off the document root and re-resolve when the theme attribute flips.
function useChartTokens() {
    const [tokens, setTokens] = useState({
        grid: "#e4e4e7",
        tick: "#71717a",
        cursor: "#d4d4d8",
        accent: "#2563eb",
        cellStroke: "#ffffff",
        tooltipLabel: "#52525b",
        dark: false,
    });

    useEffect(() => {
        const read = () => {
            const cs = getComputedStyle(document.documentElement);
            const v = (name: string, fallback: string) =>
                cs.getPropertyValue(name).trim() || fallback;
            setTokens({
                grid: v("--border-default", "#e4e4e7"),
                tick: v("--text-subtle", "#71717a"),
                cursor: v("--border-emphasis", "#d4d4d8"),
                accent: v("--accent", "#2563eb"),
                cellStroke: v("--bg-elevated", "#ffffff"),
                tooltipLabel: v("--text-muted", "#52525b"),
                dark: document.documentElement.getAttribute("data-theme") === "dark",
            });
        };
        read();
        // A single theme toggle can fire several attribute mutations in a burst;
        // debounce so we re-resolve tokens (and re-render the chart) once, after
        // the CSS vars settle, instead of 10+ times.
        let debounce: ReturnType<typeof setTimeout>;
        const observer = new MutationObserver(() => {
            clearTimeout(debounce);
            debounce = setTimeout(read, 200);
        });
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["data-theme"],
        });
        return () => {
            clearTimeout(debounce);
            observer.disconnect();
        };
    }, []);

    return tokens;
}

function categoryColor(name: string, dark: boolean): string {
    const pair = CATEGORY_COLORS[name];
    if (!pair) return dark ? "#a1a1aa" : "#71717a";
    return dark ? pair[1] : pair[0];
}

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

function TrendsChartImpl({ data }: TrendsChartProps) {
    const t = useChartTokens();

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
                        <stop offset="0%" stopColor={t.accent} stopOpacity={0.18} />
                        <stop offset="100%" stopColor={t.accent} stopOpacity={0} />
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={t.grid} />
                <XAxis
                    dataKey="month"
                    tick={{ fill: t.tick, fontSize: 12 }}
                    axisLine={{ stroke: t.grid }}
                    tickLine={false}
                />
                <YAxis
                    allowDecimals={false}
                    tick={{ fill: t.tick, fontSize: 12 }}
                    axisLine={{ stroke: t.grid }}
                    tickLine={false}
                />
                <Tooltip
                    contentStyle={tooltipStyle}
                    labelStyle={{ color: t.tooltipLabel }}
                    cursor={{ stroke: t.cursor, strokeDasharray: "3 3" }}
                />
                <Area
                    type="monotone"
                    dataKey="count"
                    stroke={t.accent}
                    strokeWidth={2}
                    fill="url(#trendGradient)"
                    name="Uploads"
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}

// Memoized: the analytics page re-renders on theme toggles / query settles, but
// these charts only need to re-render when their `data` reference changes.
const TrendsChart = React.memo(TrendsChartImpl);
export default TrendsChart;

function CategoryDonutImpl({ data }: { data: CategoryDatum[] }) {
    const t = useChartTokens();

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
                                fill={categoryColor(entry.name, t.dark)}
                                stroke={t.cellStroke}
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
                            style={{ backgroundColor: categoryColor(entry.name, t.dark) }}
                        />
                        <span className="text-xs capitalize" style={{ color: "var(--text-secondary)" }}>{entry.name}</span>
                        <span className="text-xs tabular-nums" style={{ color: "var(--text-muted)" }}>{entry.value}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export const CategoryDonut = React.memo(CategoryDonutImpl);
