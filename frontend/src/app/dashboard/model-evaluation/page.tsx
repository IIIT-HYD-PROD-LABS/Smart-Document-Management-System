"use client";

import { useEffect, useState } from "react";
import { mlApi } from "@/lib/api";
import { LoadingSpinner } from "@/components";
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
    if (value >= 0.85) return "text-[#10b981]";
    if (value >= 0.70) return "text-[#f59e0b]";
    return "text-[#ef4444]";
}

function accuracyBgColor(value: number): string {
    if (value >= 0.85) return "bg-[#10b981]/10 text-[#10b981]";
    if (value >= 0.70) return "bg-[#f59e0b]/10 text-[#f59e0b]";
    return "bg-[#ef4444]/10 text-[#ef4444]";
}

export default function ModelEvaluationPage() {
    const [report, setReport] = useState<EvaluationReport | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <LoadingSpinner />
            </div>
        );
    }

    if (error || !report) {
        return (
            <div>
                <div className="mb-8">
                    <h1 className="text-lg font-semibold text-white">Model Evaluation Report</h1>
                    <p className="text-sm text-[#52525b] mt-1">Classification model performance metrics</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg py-16 text-center">
                    <FiBarChart2 className="w-8 h-8 mx-auto mb-3 text-[#52525b]" />
                    <p className="text-sm text-[#52525b]">{error || "No report data available."}</p>
                </div>
            </div>
        );
    }

    const categories = report.categories || Object.keys(report.classification_report);

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-lg font-semibold text-white">Model Evaluation Report</h1>
                <p className="text-sm text-[#52525b] mt-1">Classification model performance metrics</p>
            </div>

            {/* Overall Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-4">
                    <p className="text-xs text-[#52525b] mb-1">Test Accuracy</p>
                    <p className={`text-xl font-semibold ${accuracyColor(report.test_accuracy)}`}>
                        {(report.test_accuracy * 100).toFixed(1)}%
                    </p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-4">
                    <p className="text-xs text-[#52525b] mb-1">CV Score</p>
                    <p className="text-xl font-semibold text-white">
                        {(report.cv_mean * 100).toFixed(1)}%
                        <span className="text-xs text-[#52525b] ml-1">+/-{(report.cv_std * 100).toFixed(1)}</span>
                    </p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-4">
                    <p className="text-xs text-[#52525b] mb-1">Best Model</p>
                    <p className="text-sm font-semibold text-white">{report.best_model}</p>
                </div>
                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-4">
                    <p className="text-xs text-[#52525b] mb-1">Total Samples</p>
                    <p className="text-xl font-semibold text-white">{report.total_samples.toLocaleString()}</p>
                    <p className="text-[10px] text-[#52525b]">{report.data_source}</p>
                </div>
            </div>

            {/* Data Split */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg p-4 mb-8">
                <h2 className="text-sm font-medium text-white mb-3">Data Split</h2>
                <div className="flex gap-6 text-xs">
                    <div>
                        <span className="text-[#52525b]">Train:</span>{" "}
                        <span className="text-white">{report.train_size}</span>
                    </div>
                    <div>
                        <span className="text-[#52525b]">Validation:</span>{" "}
                        <span className="text-white">{report.val_size}</span>
                    </div>
                    <div>
                        <span className="text-[#52525b]">Test:</span>{" "}
                        <span className="text-white">{report.test_size}</span>
                    </div>
                    <div>
                        <span className="text-[#52525b]">Vocabulary:</span>{" "}
                        <span className="text-white">{report.vocabulary_size?.toLocaleString()}</span>
                    </div>
                </div>
            </div>

            {/* Per-Category Metrics Table */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-hidden mb-8">
                <div className="px-4 py-3 border-b border-[#1f1f23]">
                    <h2 className="text-sm font-medium text-white">Per-Category Metrics</h2>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-[#52525b] text-xs border-b border-[#1f1f23]">
                                <th className="text-left px-4 py-2 font-medium">Category</th>
                                <th className="text-right px-4 py-2 font-medium">Precision</th>
                                <th className="text-right px-4 py-2 font-medium">Recall</th>
                                <th className="text-right px-4 py-2 font-medium">F1-Score</th>
                                <th className="text-right px-4 py-2 font-medium">Support</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#1f1f23]">
                            {categories.map((cat) => {
                                const m = report.classification_report[cat];
                                if (!m) return null;
                                return (
                                    <tr key={cat} className="hover:bg-[#18181b] transition-colors">
                                        <td className="px-4 py-2 text-white capitalize">{cat}</td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs ${accuracyBgColor(m.precision)}`}>
                                                {(m.precision * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs ${accuracyBgColor(m.recall)}`}>
                                                {(m.recall * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right">
                                            <span className={`px-1.5 py-0.5 rounded text-xs ${accuracyBgColor(m["f1-score"])}`}>
                                                {(m["f1-score"] * 100).toFixed(0)}%
                                            </span>
                                        </td>
                                        <td className="px-4 py-2 text-right text-[#a1a1aa]">{m.support}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Confusion Matrix */}
            <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-hidden">
                <div className="px-4 py-3 border-b border-[#1f1f23]">
                    <h2 className="text-sm font-medium text-white">Confusion Matrix</h2>
                    <p className="text-[10px] text-[#52525b] mt-0.5">Rows = actual, Columns = predicted</p>
                </div>
                <div className="overflow-x-auto p-4">
                    <table className="text-xs">
                        <thead>
                            <tr>
                                <th className="px-2 py-1" />
                                {categories.map((cat) => (
                                    <th key={cat} className="px-2 py-1 text-[#52525b] font-medium capitalize text-center min-w-[48px]">
                                        {cat.slice(0, 4)}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {report.confusion_matrix.map((row, i) => (
                                <tr key={i}>
                                    <td className="px-2 py-1 text-[#a1a1aa] font-medium capitalize">{categories[i]}</td>
                                    {row.map((val, j) => {
                                        const isCorrect = i === j;
                                        const maxInRow = Math.max(...row);
                                        const intensity = maxInRow > 0 ? val / maxInRow : 0;
                                        return (
                                            <td
                                                key={j}
                                                className={`px-2 py-1 text-center rounded ${
                                                    isCorrect && val > 0
                                                        ? "bg-[#10b981]/20 text-[#10b981] font-medium"
                                                        : val > 0
                                                        ? `text-[#a1a1aa]`
                                                        : "text-[#3f3f46]"
                                                }`}
                                                style={
                                                    !isCorrect && val > 0
                                                        ? { backgroundColor: `rgba(239, 68, 68, ${intensity * 0.15})` }
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
