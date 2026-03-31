"use client";

import { FiArrowRight, FiLock, FiActivity, FiShield } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";

const trustItems = [
    { icon: FiLock, label: "Bank-grade Encryption" },
    { icon: FiActivity, label: "99.9% Uptime" },
    { icon: FiShield, label: "SOC 2 Ready" },
];

export default function Hero({ onRequestAccess }: { onRequestAccess: () => void }) {
    return (
        <section className="pt-32 pb-20 px-6">
            <div className="max-w-2xl mx-auto text-center">
                <AnimatedSection>
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[#27272a] text-[#a1a1aa] text-xs mb-8">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                        AI-powered compliance
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.1}>
                    <h1 className="text-4xl md:text-5xl font-semibold leading-tight tracking-tight text-white mb-5">
                        Stop Missing Deadlines.<br />
                        <span className="text-[#10b981]">Master Every Notice.</span>
                    </h1>
                </AnimatedSection>

                <AnimatedSection delay={0.2}>
                    <p className="text-base text-[#71717a] max-w-md mx-auto mb-10 leading-relaxed">
                        AI classifies compliance notices, tracks deadlines across GST, IT, MCA, RBI & SEBI, and drafts responses — so no penalty slips through.
                    </p>
                </AnimatedSection>

                <AnimatedSection delay={0.3}>
                    <div className="flex items-center justify-center gap-3 mb-12">
                        <button onClick={onRequestAccess} className="px-6 py-2.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors flex items-center gap-2 cursor-pointer">
                            Join Early Access <FiArrowRight className="w-3.5 h-3.5" />
                        </button>
                        <a href="#process" className="px-6 py-2.5 text-sm text-[#a1a1aa] hover:text-white border border-[#27272a] rounded-md hover:border-[#3f3f46] transition-colors cursor-pointer">
                            See how it works
                        </a>
                    </div>
                </AnimatedSection>

                <AnimatedSection delay={0.4}>
                    <div className="flex items-center justify-center gap-6 flex-wrap">
                        {trustItems.map((item) => (
                            <div key={item.label} className="flex items-center gap-1.5 text-xs text-[#52525b]">
                                <item.icon className="w-3.5 h-3.5" />
                                {item.label}
                            </div>
                        ))}
                    </div>
                </AnimatedSection>
            </div>
        </section>
    );
}
