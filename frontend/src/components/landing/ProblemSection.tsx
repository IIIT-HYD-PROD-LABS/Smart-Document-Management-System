"use client";

import { FiClock, FiAlertTriangle, FiShield } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { testimonial } from "./data";

const painPoints = [
    {
        icon: FiClock,
        title: "40 hours lost every month",
        description:
            "Finance teams spend a full work-week each month renaming, tagging, and filing documents by hand. During audits, finding the right invoice means hours of digging through drives and email.",
    },
    {
        icon: FiAlertTriangle,
        title: "Rs.45,000 per missed filing",
        description:
            "78% of Indian SMEs miss at least one regulatory deadline every year. A single late GST return attracts Rs.50 per day plus 18% annual interest. Across five authorities, the penalties add up fast.",
    },
    {
        icon: FiShield,
        title: "No system of record",
        description:
            "When a notice arrives from GST, Income Tax, or MCA, there is no central place tracking who received it, when the deadline is, or whether anyone responded. Critical notices get buried in someone's inbox.",
    },
];

export default function ProblemSection() {
    return (
        <section id="problem" className="py-24 px-6 bg-[#09090b] scroll-mt-20">
            <div className="max-w-5xl mx-auto">
                {/* Label + Heading */}
                <AnimatedSection>
                    <div className="text-center mb-16">
                        <p className="text-xs uppercase tracking-widest text-[#52525b] mb-4">
                            [ THE PROBLEM ]
                        </p>
                        <h2
                            className="text-2xl md:text-3xl font-semibold mb-3"
                            style={{
                                background:
                                    "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255,255,255,0.6))",
                                WebkitBackgroundClip: "text",
                                WebkitTextFillColor: "transparent",
                                backgroundClip: "text",
                                letterSpacing: "-0.03em",
                            }}
                        >
                            What manual workflows actually cost
                        </h2>
                    </div>
                </AnimatedSection>

                {/* Pain Point Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
                    {painPoints.map((point, i) => (
                        <AnimatedSection key={point.title} delay={i * 0.1}>
                            <div className="group bg-[#111113] border border-[#27272a] rounded-xl p-6 h-full flex flex-col hover:border-[#3f3f46] transition-all duration-300">
                                <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0 mb-4">
                                    <point.icon className="w-[18px] h-[18px] text-red-400" />
                                </div>
                                <h3 className="text-base font-medium text-white mb-3">
                                    {point.title}
                                </h3>
                                <p className="text-sm text-[#71717a] leading-relaxed">
                                    {point.description}
                                </p>
                            </div>
                        </AnimatedSection>
                    ))}
                </div>

                {/* Testimonial */}
                <AnimatedSection delay={0.35}>
                    <div className="bg-[#0f0f12] border border-[#27272a] rounded-xl p-8 md:p-10 max-w-3xl mx-auto">
                        <p className="text-sm md:text-base text-[#a1a1aa] leading-relaxed italic mb-6">
                            &quot;{testimonial.quote}&quot;
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
