"use client";

import { FiClock, FiAlertTriangle, FiShield } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { testimonial } from "./data";

const painPoints = [
    {
        icon: FiClock,
        title: "40 Hours Lost Monthly",
        description:
            "Finance teams spend 40+ hours per month manually sorting invoices, contracts, and tax forms across drives, inboxes, and filing cabinets. Finding the right document during an audit means hours of searching.",
    },
    {
        icon: FiAlertTriangle,
        title: "\u20B945,000+ Per Missed Filing",
        description:
            "78% of Indian SMEs miss at least one filing deadline per year. A single late GST return attracts \u20B950/day penalty plus 18% annual interest. Across 200+ compliance checkpoints, the risk compounds.",
    },
    {
        icon: FiShield,
        title: "Zero Audit Trail",
        description:
            "When notices arrive from GST, Income Tax, or MCA, there\u2019s no central system tracking who received it, what the deadline is, or whether a response was filed. Critical notices get buried in email.",
    },
];

export default function ProblemSection() {
    return (
        <section id="problem" className="py-24 px-6 bg-[#09090b] scroll-mt-20">
            <div className="max-w-5xl mx-auto">
                {/* Heading */}
                <AnimatedSection>
                    <div className="text-center mb-16">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            The Cost of Manual Workflows
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-xl mx-auto leading-relaxed">
                            Indian businesses lose revenue to unorganized documents and
                            missed compliance deadlines. Here is what that actually looks
                            like.
                        </p>
                    </div>
                </AnimatedSection>

                {/* Pain Point Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
                    {painPoints.map((point, i) => (
                        <AnimatedSection key={point.title} delay={i * 0.1}>
                            <div className="bg-[#111113] border border-[#27272a] rounded-lg p-8 h-full flex flex-col">
                                <div className="flex items-center gap-3 mb-4">
                                    <div className="w-9 h-9 rounded-md bg-red-500/10 flex items-center justify-center shrink-0">
                                        <point.icon className="w-4 h-4 text-red-400" />
                                    </div>
                                    <h3 className="text-base font-medium text-white">
                                        {point.title}
                                    </h3>
                                </div>
                                <p className="text-sm text-[#71717a] leading-relaxed">
                                    {point.description}
                                </p>
                            </div>
                        </AnimatedSection>
                    ))}
                </div>

                {/* Testimonial */}
                <AnimatedSection delay={0.35}>
                    <div className="bg-[#111113] border border-[#27272a] rounded-lg p-8 md:p-10 max-w-3xl mx-auto">
                        <p className="text-sm md:text-base text-[#a1a1aa] leading-relaxed italic mb-6">
                            &ldquo;{testimonial.quote}&rdquo;
                        </p>
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-full bg-[#10b981]/10 flex items-center justify-center text-xs font-medium text-[#10b981]">
                                {testimonial.initials}
                            </div>
                            <div>
                                <p className="text-sm font-medium text-white">
                                    {testimonial.author}
                                </p>
                                <p className="text-xs text-[#52525b]">
                                    {testimonial.role}
                                </p>
                            </div>
                        </div>
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
