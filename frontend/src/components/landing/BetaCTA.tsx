"use client";

import { FiArrowRight, FiCheck } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";

interface BetaCTAProps {
    onRequestAccess: () => void;
}

const trustPoints = [
    "Free during beta",
    "No credit card",
    "Cancel anytime",
];

export default function BetaCTA({ onRequestAccess }: BetaCTAProps) {
    return (
        <section className="py-24 px-6 bg-[#0f0f12] border-t border-b border-[#27272a]">
            <div className="max-w-2xl mx-auto text-center">
                <AnimatedSection>
                    <h2
                        className="text-2xl md:text-3xl font-semibold tracking-tight mb-4"
                        style={{
                            background: "linear-gradient(to bottom, #ffffff, #ffffff, rgba(255,255,255,0.6))",
                            WebkitBackgroundClip: "text",
                            WebkitTextFillColor: "transparent",
                            backgroundClip: "text",
                            letterSpacing: "-0.03em",
                        }}
                    >
                        Join the beta
                    </h2>
                </AnimatedSection>

                <AnimatedSection delay={0.1}>
                    <p className="text-sm text-[#71717a] max-w-md mx-auto leading-relaxed mb-8">
                        Get early access to AI-powered document classification and
                        compliance tracking. Free during beta, no credit card required.
                    </p>
                </AnimatedSection>

                <AnimatedSection delay={0.2}>
                    <button
                        onClick={onRequestAccess}
                        className="group px-8 py-3 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors inline-flex items-center gap-2 cursor-pointer"
                    >
                        Request Beta Access
                        <FiArrowRight className="w-3.5 h-3.5 transition-transform duration-200 group-hover:translate-x-0.5" />
                    </button>
                </AnimatedSection>

                <AnimatedSection delay={0.3}>
                    <div className="flex items-center justify-center gap-6 mt-8 flex-wrap">
                        {trustPoints.map((point) => (
                            <div
                                key={point}
                                className="flex items-center gap-1.5 text-xs text-[#52525b]"
                            >
                                <FiCheck className="w-3 h-3 text-[#10b981] flex-shrink-0" />
                                {point}
                            </div>
                        ))}
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
