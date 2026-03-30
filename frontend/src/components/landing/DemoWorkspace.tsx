"use client";

import AnimatedSection from "./AnimatedSection";
import { demoNotices, authorityColors, riskColors, statusColors } from "./data";

export default function DemoWorkspace() {
    return (
        <section id="demo" className="pb-24 px-6 scroll-mt-20">
            <div className="max-w-4xl mx-auto">
                <AnimatedSection>
                    <div className="text-center mb-8">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            The Compliance Workspace
                        </h2>
                        <p className="text-sm text-[#71717a]">
                            Every notice, every deadline, every authority — in one view.
                        </p>
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.15}>
                    <div className="bg-[#111113] border border-[#27272a] rounded-lg overflow-hidden">
                        <div className="flex items-center justify-between px-5 py-3 border-b border-[#1f1f23]">
                            <span className="text-xs text-[#a1a1aa]">Showing <span className="text-white font-medium">5</span> of 1,247 notices</span>
                            <div className="flex items-center gap-2">
                                <span className="text-[10px] px-2 py-0.5 rounded-full border border-[#27272a] text-[#52525b]">All Entities</span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full border border-[#27272a] text-[#52525b]">All Authorities</span>
                            </div>
                        </div>

                        <div className="overflow-x-auto">
                            <table className="w-full text-left">
                                <thead>
                                    <tr className="border-b border-[#1f1f23]">
                                        {["Date", "Authority", "Type", "Risk", "Status", "Deadline"].map((h) => (
                                            <th key={h} className="px-5 py-3 text-[11px] font-medium text-[#52525b] uppercase tracking-wider">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {demoNotices.map((n, i) => {
                                        const auth = authorityColors[n.authority];
                                        const risk = riskColors[n.risk];
                                        const status = statusColors[n.status];
                                        return (
                                            <tr key={i} className="border-b border-[#1f1f23] last:border-0 hover:bg-[#0f0f12] transition-colors">
                                                <td className="px-5 py-3.5 text-sm text-[#a1a1aa] font-mono tabular-nums">{n.date}</td>
                                                <td className="px-5 py-3.5">
                                                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${auth.bg} ${auth.text}`}>
                                                        {n.authority}
                                                    </span>
                                                </td>
                                                <td className="px-5 py-3.5 text-sm text-white">{n.type}</td>
                                                <td className="px-5 py-3.5">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${risk.bg} ${risk.text}`}>
                                                            {n.risk}
                                                        </span>
                                                        <span className="text-[11px] text-[#52525b] font-mono">{n.riskScore}</span>
                                                    </div>
                                                </td>
                                                <td className="px-5 py-3.5">
                                                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded ${status.bg} ${status.text}`}>
                                                        {n.status}
                                                    </span>
                                                </td>
                                                <td className="px-5 py-3.5 text-sm text-[#a1a1aa] font-mono tabular-nums">{n.deadline}</td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>

                        <div className="flex items-center justify-between px-5 py-3 border-t border-[#1f1f23]">
                            <span className="text-[11px] text-[#52525b]">3 entities across 5 authorities</span>
                            <span className="text-[11px] text-[#10b981]">2 deadlines within 7 days</span>
                        </div>
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
