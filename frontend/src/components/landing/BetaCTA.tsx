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
        <section className="pb-24 px-6">
            <div className="max-w-2xl mx-auto">
                <AnimatedSection>
                    <div className="bg-[#0f0f12] border border-[#27272a] rounded-lg p-10 md:p-14 text-center">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-4">
                            Join the Beta
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-md mx-auto leading-relaxed mb-8">
                            Get early access to AI-powered document classification and
                            compliance tracking. Free during beta. No credit card
                            required.
                        </p>

                        <button
                            onClick={onRequestAccess}
                            className="px-8 py-3 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors flex items-center gap-2 mx-auto cursor-pointer"
                        >
                            Request Beta Access
                            <FiArrowRight className="w-3.5 h-3.5" />
                        </button>

                        <div className="flex items-center justify-center gap-6 mt-6 flex-wrap">
                            {trustPoints.map((point) => (
                                <div
                                    key={point}
                                    className="flex items-center gap-1.5 text-xs text-[#52525b]"
                                >
                                    <FiCheck className="w-3 h-3 text-[#10b981]" />
                                    {point}
                                </div>
                            ))}
                        </div>
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
