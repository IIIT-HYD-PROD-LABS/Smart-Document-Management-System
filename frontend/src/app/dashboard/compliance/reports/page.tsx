"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiBarChart2, FiPlay } from "react-icons/fi";
import { useCurrentClient } from "@/stores/currentClientStore";
import { complianceApi } from "@/lib/api/compliance";

/**
 * Reports — UI-SPEC §reports + CLIENT-07.
 *
 * Renders monthly health summary metrics structurally as React JSX. The
 * backend's `summary_html` string is shown inside a `<details><pre>` block
 * with `whitespace-pre-wrap` — never injected via React's raw-HTML prop.
 * This eliminates the XSS surface for backend-generated HTML even though
 * the source is currently trusted.
 */

interface HealthSummary {
    metrics: Record<string, number | string>;
    summary_html: string;
}

function currentMonth(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default function ReportsPage() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const [month, setMonth] = useState<string>(currentMonth());
    const [summary, setSummary] = useState<HealthSummary | null>(null);

    const generate = useMutation({
        mutationFn: async (): Promise<HealthSummary> => {
            if (activeClientId === null)
                throw new Error("Select a client first.");
            const res = await complianceApi.healthSummary({
                client_id: activeClientId,
                month: `${month}-01`,
            });
            return res.data as HealthSummary;
        },
        onSuccess: (data) => {
            setSummary(data);
            toast.success("Report generated");
        },
        onError: (err) =>
            toast.error(
                err instanceof Error ? err.message : "Could not generate report"
            ),
    });

    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <header className="mb-6 flex items-start gap-3">
                <FiBarChart2
                    className="w-5 h-5 text-[#3b82f6] mt-0.5 shrink-0"
                    aria-hidden="true"
                />
                <div>
                    <h1 className="text-lg font-semibold text-white mb-0.5">
                        Reports
                    </h1>
                    <p className="text-[13px] text-[#71717a]">
                        Generate a monthly compliance health summary on demand.
                    </p>
                </div>
            </header>

            {activeClientId === null ? (
                <div className="bg-[#111113] border border-[#27272a] rounded-md p-12 text-center">
                    <h2 className="text-sm font-semibold text-white mb-1">
                        No client selected
                    </h2>
                    <p className="text-[13px] text-[#71717a]">
                        Select a client from the switcher to generate reports.
                    </p>
                </div>
            ) : (
                <>
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            generate.mutate();
                        }}
                        className="bg-[#111113] border border-[#27272a] rounded-md p-4 mb-6 flex items-end gap-3 flex-wrap"
                    >
                        <div className="flex-1 min-w-[180px]">
                            <label
                                htmlFor="report-month"
                                className="block text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1.5"
                            >
                                Month
                            </label>
                            <input
                                id="report-month"
                                type="month"
                                value={month}
                                onChange={(e) => setMonth(e.target.value)}
                                required
                                className="w-full bg-[#18181b] border border-[#27272a] rounded px-2.5 py-1.5 text-[13px] text-white focus:outline-none focus:border-[#3f3f46] focus:ring-1 focus:ring-[#3b82f6]/40"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={generate.isPending}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#3b82f6] text-white text-[12px] font-medium hover:bg-[#2563eb] disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40"
                        >
                            <FiPlay className="w-3.5 h-3.5" />
                            {generate.isPending ? "Generating…" : "Generate"}
                        </button>
                    </form>

                    {summary && (
                        <div className="bg-[#111113] border border-[#27272a] rounded-md p-6">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                                {Object.entries(summary.metrics).map(
                                    ([k, v]) => (
                                        <div
                                            key={k}
                                            className="bg-[#18181b] rounded p-4"
                                        >
                                            <div className="text-[11px] uppercase tracking-wider text-[#a1a1aa] mb-1">
                                                {k.replace(/_/g, " ")}
                                            </div>
                                            <div className="text-2xl font-semibold text-white tabular-nums">
                                                {v}
                                            </div>
                                        </div>
                                    )
                                )}
                            </div>
                            <details className="border-t border-[#27272a] pt-4">
                                <summary className="text-[11px] uppercase tracking-wider text-[#a1a1aa] cursor-pointer hover:text-white focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40 rounded">
                                    Raw HTML (debug)
                                </summary>
                                <pre className="mt-2 text-xs text-[#71717a] font-mono whitespace-pre-wrap bg-[#18181b] rounded p-3 overflow-x-auto">
                                    {summary.summary_html}
                                </pre>
                            </details>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
