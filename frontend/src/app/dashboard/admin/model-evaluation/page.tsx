"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { mlApi } from "@/lib/api";
import { Skeleton } from "@/components";
import { useAuth } from "@/context/AuthContext";
import { FiBarChart2 } from "react-icons/fi";

interface CategoryMetrics {
    precision: number;
    recall: number;
    "f1-score": number;
    support: number;
}

interface EvaluationReport {
    data_source: string;
    total_samples: number;
    train_size: number;
    val_size: number;
    test_size: number;
    best_model: string;
    test_accuracy: number;
    cv_mean: number;
    cv_std: number;
    vocabulary_size: number;
    classification_report: Record<string, CategoryMetrics>;
    confusion_matrix: number[][];
    categories: string[];
}

function accuracyColor(value: number): string {
    if (value >= 0.85) return "text-[var(--success)]";
    if (value >= 0.70) return "text-[var(--warning)]";
    return "text-[var(--danger)]";
}

function accuracyBgColor(value: number): string {
    if (value >= 0.85) return "bg-[var(--success-soft)] text-[var(--success)]";
    if (value >= 0.70) return "bg-[var(--warning-soft)] text-[var(--warning)]";
    return "bg-[var(--danger-soft)] text-[var(--danger)]";
}

export default function ModelEvaluationPage() {
    const { user, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const [report, setReport] = useState<EvaluationReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Admin-only route. Backend require_admin gate already returns 403,
    // but the page should not render at all for non-admins (matches the
    // pattern in /dashboard/admin/page.tsx and /compliance/clients/page.tsx).
    useEffect(() => {
        if (!authLoading && user && user.role !== "admin") {
            router.replace("/dashboard");
        }
    }, [authLoading, user, router]);

    useEffect(() => {
        const fetchReport = async () => {
            try {
                const res = await mlApi.getEvaluation();
                setReport(res.data);
            } catch (err: unknown) {
                if ((err as { response?: { status?: number } })?.response?.status === 404) {
                    setError("No evaluation report available. Train the model first to generate metrics.");
                } else {
                    setError("Failed to load evaluation report.");
                }
            } finally {
                setLoading(false);
            }
        };
        fetchReport();
    }, []);

    // Render-time guard so non-admins don't see metrics for the brief
    // window before the redirect fires. Placed AFTER all hooks.
    if (!authLoading && user && user.role !== "admin") return null;

    if (loading) {
        return (
            <div role="status" aria-busy="true" aria-live="polite">
                <span className="sr-only">Loading model evaluation report</span>
                <div className="mb-8">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Model Evaluation Report</h1>
                    <p className="text-sm text-[var(--text-muted)] mt-1">Classification model performance metrics</p>
                </div>

                {/* Overall Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4">
                            <Skeleton className="h-3 w-20 mb-2" />
                            <Skeleton className="h-7 w-16" />
                        </div>
                    ))}
                </div>

                {/* Data Split */}
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4 mb-8">
                    <Skeleton className="h-4 w-24 mb-3" />
                    <div className="flex flex-wrap gap-6">
                        {Array.from({ length: 4 }).map((_, i) => (
                            <Skeleton key={i} className="h-4 w-28" />
                        ))}
                    </div>
                </div>

                {/* Per-Category Metrics Table */}
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg overflow-hidden mb-8">
                    <div className="px-4 py-3 border-b border-[var(--border-default)]">
                        <Skeleton className="h-4 w-40" />
                    </div>
                    <div className="p-4 space-y-3">
                        {Array.from({ length: 6 }).map((_, i) => (
                            <Skeleton key={i} className="h-6 w-full" />
                        ))}
                    </div>
                </div>

                {/* Confusion Matrix */}
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg overflow-hidden">
                    <div className="px-4 py-3 border-b border-[var(--border-default)]">
                        <Skeleton className="h-4 w-36 mb-1" />
                        <Skeleton className="h-3 w-48" />
                    </div>
                    <div className="p-4 space-y-3">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <Skeleton key={i} className="h-6 w-full" />
                        ))}
                    </div>
                </div>
            </div>
        );
    }

    if (error || !report) {
        return (
            <div>
                <div className="mb-8">
                    <h1 className="text-lg font-semibold text-[var(--text-primary)]">Model Evaluation Report</h1>
                    <p className="text-sm text-[var(--text-muted)] mt-1">Classification model performance metrics</p>
                </div>
                <div className="bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-lg py-16 text-center">
                    <FiBarChart2 className="w-8 h-8 mx-auto mb-3 text-[var(--text-subtle)]" />
                    <p className="text-sm text-[var(--text-muted)]">{error || "No report data available."}</p>
                </div>
            </div>
        );
    }

    const categories = report.categories || Object.keys(report.classification_report);

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-[var(--text-primary)]">Model Evaluation Report</h1>
                <p className="text-sm text-[var(--text-muted)] mt-1">Classification model performance metrics</p>
            </div>

            {/* Overall Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4">
                    <p className="text-xs text-[var(--text-muted)] mb-1">Test Accuracy</p>
                    <p className={`text-xl font-semibold ${accuracyColor(report.test_accuracy)}`}>
                        {(report.test_accuracy * 100).toFixed(1)}%
                    </p>
                </div>
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4">
                    <p className="text-xs text-[var(--text-muted)] mb-1">CV Score</p>
                    <p className="text-xl font-semibold text-[var(--text-primary)]">
                        {(report.cv_mean * 100).toFixed(1)}%
                        <span className="text-xs text-[var(--text-muted)] ml-1">+/-{(report.cv_std * 100).toFixed(1)}</span>
                    </p>
                </div>
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4">
                    <p className="text-xs text-[var(--text-muted)] mb-1">Best Model</p>
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{report.best_model}</p>
                </div>
                <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4">
                    <p className="text-xs text-[var(--text-muted)] mb-1">Total Samples</p>
                    <p className="text-xl font-semibold text-[var(--text-primary)]">{report.total_samples.toLocaleString()}</p>
                    <p className="text-[10px] text-[var(--text-subtle)]">{report.data_source}</p>
                </div>
            </div>

            {/* Data Split */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg p-4 mb-8">
                <h2 className="text-sm font-medium text-[var(--text-primary)] mb-3">Data Split</h2>
                <div className="flex flex-wrap gap-6 text-xs">
                    <div>
                        <span className="text-[var(--text-muted)]">Train:</span>{" "}
                        <span className="text-[var(--text-primary)] font-medium">{report.train_size}</span>
                    </div>
                    <div>
                        <span className="text-[var(--text-muted)]">Validation:</span>{" "}
                        <span className="text-[var(--text-primary)] font-medium">{report.val_size}</span>
                    </div>
                    <div>
                        <span className="text-[var(--text-muted)]">Test:</span>{" "}
                        <span className="text-[var(--text-primary)] font-medium">{report.test_size}</span>
                    </div>
                    <div>
                        <span className="text-[var(--text-muted)]">Vocabulary:</span>{" "}
                        <span className="text-[var(--text-primary)] font-medium">{report.vocabulary_size?.toLocaleString()}</span>
                    </div>
                </div>
            </div>

            {/* Per-Category Metrics Table */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg overflow-hidden mb-8">
                <div className="px-4 py-3 border-b border-[var(--border-default)]">
                    <h2 className="text-sm font-medium text-[var(--text-primary)]">Per-Category Metrics</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-[var(--bg-muted)]">
                            <tr className="text-[var(--text-secondary)] text-xs border-b border-[var(--border-default)]">
                                <th className="text-left px-4 py-2 font-medium uppercase tracking-wider">Category</th>
                                <th className="text-right px-4 py-2 font-medium uppercase tracking-wider">Precision</th>
                                <th className="text-right px-4 py-2 font-medium uppercase tracking-wider">Recall</th>
                                <th className="text-right px-4 py-2 font-medium uppercase tracking-wider">F1-Score</th>
                                <th className="text-right px-4 py-2 font-medium uppercase tracking-wider">Support</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border-default)]">
                            {categories.map((cat) => {
                                const m = report.classification_report[cat];
                                if (!m) return null;
                                return (
                                    <tr key={cat} className="hover:bg-[var(--bg-hover)] transition-colors">
                                        <td className="px-4 py-2 text-[var(--text-primary)] capitalize font-medium">{cat}</td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${accuracyBgColor(m.precision)}`}>
                                                {(m.precision * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${accuracyBgColor(m.recall)}`}>
                                                {(m.recall * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${accuracyBgColor(m["f1-score"])}`}>
                                                {(m["f1-score"] * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right text-[var(--text-muted)] tabular-nums">{m.support}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Confusion Matrix */}
            <div className="bg-[var(--bg-surface)] border border-[var(--border-default)] rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-[var(--border-default)]">
                    <h2 className="text-sm font-medium text-[var(--text-primary)]">Confusion Matrix</h2>
                    <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Rows = actual, Columns = predicted</p>
                </div>
                <div className="overflow-x-auto p-4">
                    <table className="text-xs">
                        <thead>
                            <tr>
                                <th className="px-2 py-1" />
                                {categories.map((cat) => (
                                    <th key={cat} className="px-2 py-1 text-[var(--text-muted)] font-medium capitalize text-center min-w-[48px]">
                                        {cat.slice(0, 4)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {report.confusion_matrix.map((row, i) => (
                                <tr key={i}>
                                    <td className="px-2 py-1 text-[var(--text-secondary)] font-medium capitalize">{categories[i]}</td>
                                    {row.map((val, j) => {
                                        const isCorrect = i === j;
                                        const maxInRow = Math.max(...row);
                                        const intensity = maxInRow > 0 ? val / maxInRow : 0;
                                        return (
                                            <td
                                                key={j}
                                                className={`px-2 py-1 text-center rounded tabular-nums ${
                                                    isCorrect && val > 0
                                                        ? "bg-[var(--success-soft)] text-[var(--success)] font-semibold"
                                                        : val > 0
                                                        ? "text-[var(--text-secondary)]"
                                                        : "text-[var(--text-subtle)]"
                                                }`}
                                                style={
                                                    !isCorrect && val > 0
                                                        ? { backgroundColor: `rgba(185, 28, 28, ${intensity * 0.12})` }
                                                        : undefined
                                                }
                                            >
                                                {val}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
