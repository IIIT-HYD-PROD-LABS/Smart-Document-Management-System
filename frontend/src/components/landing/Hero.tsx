"use client";

import { FiArrowRight } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";

export default function Hero({ onRequestAccess }: { onRequestAccess: () => void }) {
    return (
        <section className="relative pt-32 pb-24 px-6 overflow-hidden">
            {/* Subtle radial glow behind hero */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-[#10b981]/5 rounded-full blur-[120px] pointer-events-none" />

            <div className="max-w-2xl mx-auto text-center relative z-10">
                <AnimatedSection>
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#27272a] text-[#a1a1aa] text-xs mb-8">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                        Built for CA firms and finance teams
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.1}>
                    <h1
                        className="text-4xl md:text-5xl lg:text-[3.5rem] font-semibold leading-[1.1] mb-6"
                        style={{
                            background: "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255,255,255,0.6))",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            backgroundClip: "text",
                            letterSpacing: "-0.05em",
                        }}
                    >
                        AI that classifies your documents and tracks every compliance notice
                    </h1>
                </AnimatedSection>

                <AnimatedSection delay={0.2}>
                    <p className="text-base text-[#71717a] max-w-lg mx-auto mb-10 leading-relaxed">
                        Upload invoices, contracts, or regulatory notices. TaxSync classifies them in seconds,
                        extracts the data that matters, and makes sure no GST, Income Tax, or MCA deadline gets missed.
                    </p>
                </AnimatedSection>

                <AnimatedSection delay={0.3}>
                    <div className="flex items-center justify-center gap-4 mb-12">
                        <button
                            onClick={onRequestAccess}
                            className="group px-7 py-2.5 text-sm font-medium bg-white text-[#09090b] rounded-lg hover:bg-[#e4e4e7] transition-all duration-200 flex items-center gap-2 cursor-pointer"
                        >
                            Join Early Access
                            <FiArrowRight className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                        </button>
                        <a
                            href="#solution"
                            className="px-7 py-2.5 text-sm text-[#a1a1aa] hover:text-white border border-[#27272a] rounded-lg hover:border-[#3f3f46] transition-all duration-200 cursor-pointer"
                        >
                            See how it works
                        </a>
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.4}>
                    <div className="flex items-center justify-center gap-4 text-[11px] text-[#52525b]">
                        <span className="flex items-center gap-1.5">
                            <span className="w-1 h-1 rounded-full bg-[#3f3f46]" />
                            No integration required
                        </span>
                        <span className="flex items-center gap-1.5">
                            <span className="w-1 h-1 rounded-full bg-[#3f3f46]" />
                            SOC 2 compliant
                        </span>
                        <span className="flex items-center gap-1.5">
                            <span className="w-1 h-1 rounded-full bg-[#3f3f46]" />
                            GDPR ready
                        </span>
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
