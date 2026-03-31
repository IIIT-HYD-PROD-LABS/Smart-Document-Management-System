"use client";

import { FiUpload, FiCpu, FiSearch, FiCheckCircle } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { docFeatures, complianceFeatures, processSteps } from "./data";

const stepIcons = [FiUpload, FiCpu, FiSearch, FiCheckCircle];

export default function ProcessFlow() {
    return (
        <section id="solution" className="bg-[#09090b] pb-24 px-6 scroll-mt-20">
            <div className="max-w-4xl mx-auto">
                {/* ---- Section heading ---- */}
                <AnimatedSection>
                    <div className="text-center mb-14">
                        <h2 className="text-2xl md:text-3xl font-semibold text-white tracking-tight mb-3">
                            Built for Document Reality
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-xl mx-auto leading-relaxed">
                            Two engines. One platform. Upload anything — documents or
                            compliance notices — and let AI handle the rest.
                        </p>
                    </div>
                </AnimatedSection>

                {/* ---- Two capability cards side-by-side ---- */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-14">
                    {/* Document Intelligence */}
                    <AnimatedSection delay={0.1}>
                        <div className="bg-[#111113] border border-[#27272a] border-l-[#10b981] border-l-2 rounded-lg p-8 h-full">
                            <h3 className="text-base font-medium text-white mb-6">
                                Document Intelligence
                            </h3>
                            <ul className="space-y-5">
                                {docFeatures.map((feature) => (
                                    <li key={feature.title} className="flex gap-3">
                                        <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#10b981]" />
                                        <div>
                                            <p className="text-sm font-medium text-white mb-0.5">
                                                {feature.title}
                                            </p>
                                            <p className="text-sm text-[#71717a] leading-relaxed">
                                                {feature.description}
                                            </p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </AnimatedSection>

                    {/* Compliance Automation */}
                    <AnimatedSection delay={0.2}>
                        <div className="bg-[#111113] border border-[#27272a] border-l-[#10b981] border-l-2 rounded-lg p-8 h-full">
                            <h3 className="text-base font-medium text-white mb-6">
                                Compliance Automation
                            </h3>
                            <ul className="space-y-5">
                                {complianceFeatures.map((feature) => (
                                    <li key={feature.title} className="flex gap-3">
                                        <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#10b981]" />
                                        <div>
                                            <p className="text-sm font-medium text-white mb-0.5">
                                                {feature.title}
                                            </p>
                                            <p className="text-sm text-[#71717a] leading-relaxed">
                                                {feature.description}
                                            </p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </AnimatedSection>
                </div>

                {/* ---- 4-step process flow ---- */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {processSteps.map((step, i) => {
                        const Icon = stepIcons[i];
                        return (
                            <AnimatedSection key={step.number} delay={0.3 + i * 0.1}>
                                <div className="bg-[#111113] border border-[#27272a] rounded-lg p-6 h-full relative">
                                    <div className="flex items-center gap-3 mb-4">
                                        <span className="text-xs font-mono font-semibold text-[#10b981]">
                                            {step.number}
                                        </span>
                                        <div className="w-7 h-7 rounded-md bg-[#10b981]/10 flex items-center justify-center">
                                            <Icon className="w-3.5 h-3.5 text-[#10b981]" />
                                        </div>
                                    </div>
                                    <h3 className="text-sm font-medium text-white mb-2">
                                        {step.title}
                                    </h3>
                                    <p className="text-sm text-[#71717a] leading-relaxed">
                                        {step.description}
                                    </p>
                                    {i < processSteps.length - 1 && (
                                        <div className="hidden lg:block absolute top-1/2 -right-2.5 w-1.5 h-1.5 rounded-full bg-[#27272a]" />
                                    )}
                                </div>
                            </AnimatedSection>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
