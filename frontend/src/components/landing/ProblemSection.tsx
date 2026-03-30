"use client";

import AnimatedSection from "./AnimatedSection";
import { stats } from "./data";

export default function ProblemSection() {
    return (
        <section id="features" className="pb-24 px-6 scroll-mt-20">
            <div className="max-w-3xl mx-auto">
                <AnimatedSection>
                    <div className="text-center mb-12">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            The Compliance Reality
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-md mx-auto">
                            Indian businesses face a dense regulatory landscape. One missed deadline can cascade into penalties, interest, and legal exposure.
                        </p>
                    </div>
                </AnimatedSection>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-[#27272a] rounded-lg overflow-hidden border border-[#27272a]">
                    {stats.map((stat, i) => (
                        <AnimatedSection key={stat.value} delay={i * 0.1}>
                            <div className="bg-[#09090b] p-8 text-center">
                                <div className="text-3xl font-semibold text-white mb-2">{stat.value}</div>
                                <p className="text-sm text-[#71717a] leading-relaxed">{stat.label}</p>
                            </div>
                        </AnimatedSection>
                    ))}
                </div>
            </div>
        </section>
    );
}
