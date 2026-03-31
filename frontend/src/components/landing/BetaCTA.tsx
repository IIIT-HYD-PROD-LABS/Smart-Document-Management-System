"use client";

import { FiArrowRight } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";

interface BetaCTAProps {
    onRequestAccess: () => void;
}

export default function BetaCTA({ onRequestAccess }: BetaCTAProps) {
    return (
        <section className="pb-24 px-6">
            <div className="max-w-2xl mx-auto text-center">
                <AnimatedSection>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[#10b981]/30 text-[#10b981] text-xs mb-6">
                        Limited Beta
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.1}>
                    <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-4">
                        Be the first to automate your document workflow
                    </h2>
                    <p className="text-sm text-[#71717a] mb-8 max-w-sm mx-auto">
                        AI-powered document classification and compliance tracking, built for teams managing GST, IT, MCA, RBI and SEBI filings.
                    </p>
                </AnimatedSection>

                <AnimatedSection delay={0.2}>
                    <button
                        onClick={onRequestAccess}
                        className="px-8 py-3 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors flex items-center gap-2 mx-auto cursor-pointer"
                    >
                        Join Early Access <FiArrowRight className="w-3.5 h-3.5" />
                    </button>
                    <p className="text-xs text-[#52525b] mt-4">No credit card required. Free during beta.</p>
                </AnimatedSection>
            </div>
        </section>
    );
}
