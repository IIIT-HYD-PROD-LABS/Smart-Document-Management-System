"use client";

import { FiArrowRight } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";

const trustBadges = [
    "No Integration Required",
    "SOC 2 Compliant",
    "GDPR Ready",
];

export default function Hero({ onRequestAccess }: { onRequestAccess: () => void }) {
    return (
        <section className="pt-32 pb-20 px-6">
            <div className="max-w-2xl mx-auto text-center">
                <AnimatedSection>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[#27272a] text-[#a1a1aa] text-xs mb-8">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                        Trusted by CA firms across India
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.1}>
                    <h1 className="text-4xl md:text-5xl font-semibold leading-tight tracking-tight text-white mb-5">
                        Stop Sorting. Let AI Classify Every Document and{" "}
                        <span className="text-[#10b981]">Track Every Notice.</span>
                    </h1>
                </AnimatedSection>

                <AnimatedSection delay={0.2}>
                    <p className="text-base text-[#71717a] max-w-md mx-auto mb-10 leading-relaxed">
                        Upload invoices, contracts, and compliance notices. AI classifies
                        them instantly, extracts key data, and tracks every deadline across
                        GST, IT, MCA, RBI and SEBI — so nothing falls through.
                    </p>
                </AnimatedSection>

                <AnimatedSection delay={0.3}>
                    <div className="flex items-center justify-center mb-10">
                        <button
                            onClick={onRequestAccess}
                            className="px-6 py-2.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors flex items-center gap-2 cursor-pointer"
                        >
                            Join Early Access <FiArrowRight className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.4}>
                    <div className="flex items-center justify-center gap-3 flex-wrap">
                        {trustBadges.map((badge) => (
                            <span
                                key={badge}
                                className="inline-flex items-center px-3 py-1 rounded-full border border-[#27272a] text-xs text-[#52525b]"
                            >
                                {badge}
                            </span>
                        ))}
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
