"use client";

import { FiUpload, FiCpu, FiBell, FiCheckCircle } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { processSteps } from "./data";

const icons = [FiUpload, FiCpu, FiBell, FiCheckCircle];

export default function ProcessFlow() {
    return (
        <section id="process" className="pb-24 px-6 scroll-mt-20">
            <div className="max-w-4xl mx-auto">
                <AnimatedSection>
                    <div className="text-center mb-12">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            Built for Compliance Reality
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-md mx-auto">
                            From notice upload to resolution — a four-step workflow that leaves nothing to chance.
                        </p>
                    </div>
                </AnimatedSection>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {processSteps.map((step, i) => {
                        const Icon = icons[i];
                        return (
                            <AnimatedSection key={step.number} delay={i * 0.1}>
                                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-6 h-full">
                                    <div className="flex items-center gap-3 mb-4">
                                        <span className="text-xs font-mono font-semibold text-[#10b981]">{step.number}</span>
                                        <Icon className="w-4 h-4 text-[#a1a1aa]" />
                                    </div>
                                    <h3 className="text-sm font-medium text-white mb-2">{step.title}</h3>
                                    <p className="text-sm text-[#71717a] leading-relaxed">{step.description}</p>
                                </div>
                            </AnimatedSection>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
