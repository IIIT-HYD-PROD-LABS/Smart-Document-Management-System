"use client";

import { FiFolder, FiAlertTriangle } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { stats } from "./data";

const problems = [
    {
        icon: FiFolder,
        title: "Document Chaos",
        description:
            "Businesses drown in unorganized documents. Invoices, contracts, tax forms, and receipts scattered across drives, inboxes, and filing cabinets. Finding the right file means hours of manual searching.",
    },
    {
        icon: FiAlertTriangle,
        title: "Compliance Risk",
        description:
            "Indian businesses face 200+ regulatory checkpoints across GST, Income Tax, MCA, RBI, and SEBI. One missed deadline cascades into penalties, interest charges, and legal exposure.",
    },
];

export default function ProblemSection() {
    return (
        <section id="features" className="pb-24 px-6 scroll-mt-20">
            <div className="max-w-4xl mx-auto">
                <AnimatedSection>
                    <div className="text-center mb-14">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            Two Problems. One Platform.
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-lg mx-auto leading-relaxed">
                            Indian businesses lose time to document disorder and money to
                            compliance penalties. TaxSync handles both.
                        </p>
                    </div>
                </AnimatedSection>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
                    {problems.map((problem, i) => (
                        <AnimatedSection key={problem.title} delay={i * 0.1}>
                            <div className="bg-[#111113] border border-[#27272a] rounded-lg p-8 h-full">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-8 h-8 rounded-md bg-[#10b981]/10 flex items-center justify-center">
                                        <problem.icon className="w-4 h-4 text-[#10b981]" />
                                    </div>
                                    <h3 className="text-base font-medium text-white">
                                        {problem.title}
                                    </h3>
                                </div>
                                <p className="text-sm text-[#71717a] leading-relaxed">
                                    {problem.description}
                                </p>
                            </div>
                        </AnimatedSection>
                    ))}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-px bg-[#27272a] rounded-lg overflow-hidden border border-[#27272a]">
                    {stats.map((stat, i) => (
                        <AnimatedSection key={stat.value} delay={i * 0.08}>
                            <div className="bg-[#09090b] p-6 md:p-8 text-center h-full">
                                <div className="text-2xl md:text-3xl font-semibold text-white mb-2">
                                    {stat.value}
                                </div>
                                <p className="text-xs md:text-sm text-[#71717a] leading-relaxed">
                                    {stat.label}
                                </p>
                            </div>
                        </AnimatedSection>
                    ))}
                </div>
            </div>
        </section>
    );
}
