"use client";

import { FiUpload, FiCpu, FiSearch, FiCheckCircle } from "react-icons/fi";
import AnimatedSection from "./AnimatedSection";
import { docFeatures, complianceFeatures, processSteps } from "./data";

const stepIcons = [FiUpload, FiCpu, FiSearch, FiCheckCircle];

export default function ProcessFlow() {
    return (
        <section id="solution" className="bg-[#09090b] pb-24 px-6 scroll-mt-20">
            <div className="max-w-5xl mx-auto">
                {/* Section heading */}
                <AnimatedSection>
                    <div className="text-center mb-14">
                        <p className="text-xs uppercase tracking-widest text-[#52525b] mb-4">
                            [ THE SOLUTION ]
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
                            Built for document reality
                        </h2>
                        <p className="text-sm text-[#71717a] max-w-xl mx-auto leading-relaxed">
                            Two engines, one platform. Upload anything and let AI handle the rest.
                        </p>
                    </div>
                </AnimatedSection>

                {/* Two capability cards side by side */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-14">
                    {/* Document Intelligence */}
                    <AnimatedSection delay={0.1}>
                        <div className="group relative bg-[#111113] border border-[#27272a] border-l-2 border-l-[#10b981] rounded-xl p-8 h-full hover:border-[#3f3f46] hover:border-l-[#10b981] transition-all duration-300">
                            {/* Corner decorators */}
                            <div className="absolute top-0 right-0 w-4 h-[2px] bg-[#10b981] rounded-tr-xl" />
                            <div className="absolute top-0 right-0 w-[2px] h-4 bg-[#10b981] rounded-tr-xl" />
                            <div className="absolute bottom-0 left-0 w-4 h-[2px] bg-[#10b981] rounded-bl-xl" />
                            <div className="absolute bottom-0 left-0 w-[2px] h-4 bg-[#10b981] rounded-bl-xl" />

                            <h3 className="text-base font-medium text-white mb-6">
                                Document Intelligence
                            </h3>
                            <ul className="space-y-5">
                                {docFeatures.map((feature) => (
                                    <li key={feature.title} className="flex gap-3">
                                        <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] mt-2 shrink-0" />
                                        <div>
                                            <p className="text-sm font-medium text-white mb-0.5">
                                                {feature.title}
                                            </p>
                                            <p className="text-sm text-[#52525b] leading-relaxed">
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
                        <div className="group relative bg-[#111113] border border-[#27272a] border-l-2 border-l-[#10b981] rounded-xl p-8 h-full hover:border-[#3f3f46] hover:border-l-[#10b981] transition-all duration-300">
                            {/* Corner decorators */}
                            <div className="absolute top-0 right-0 w-4 h-[2px] bg-[#10b981] rounded-tr-xl" />
                            <div className="absolute top-0 right-0 w-[2px] h-4 bg-[#10b981] rounded-tr-xl" />
                            <div className="absolute bottom-0 left-0 w-4 h-[2px] bg-[#10b981] rounded-bl-xl" />
                            <div className="absolute bottom-0 left-0 w-[2px] h-4 bg-[#10b981] rounded-bl-xl" />

                            <h3 className="text-base font-medium text-white mb-6">
                                Compliance Automation
                            </h3>
                            <ul className="space-y-5">
                                {complianceFeatures.map((feature) => (
                                    <li key={feature.title} className="flex gap-3">
                                        <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] mt-2 shrink-0" />
                                        <div>
                                            <p className="text-sm font-medium text-white mb-0.5">
                                                {feature.title}
                                            </p>
                                            <p className="text-sm text-[#52525b] leading-relaxed">
                                                {feature.description}
                                            </p>
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </AnimatedSection>
                </div>

                {/* 4-step process flow */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {processSteps.map((step, i) => {
                        const Icon = stepIcons[i];
                        return (
                            <AnimatedSection key={step.number} delay={0.3 + i * 0.1}>
                                <div className="group bg-[#111113] border border-[#27272a] rounded-xl p-6 h-full relative hover:border-[#3f3f46] transition-all duration-300">
                                    <div className="flex items-center gap-3 mb-4">
                                        <span className="text-xs font-mono text-[#10b981]">
                                            {step.number}
                                        </span>
                                        <div className="w-8 h-8 rounded-lg bg-[#10b981]/10 flex items-center justify-center">
                                            <Icon className="w-4 h-4 text-[#10b981]" />
                                        </div>
                                    </div>
                                    <h3 className="text-sm font-medium text-white mb-2">
                                        {step.title}
                                    </h3>
                                    <p className="text-xs text-[#52525b] leading-relaxed">
                                        {step.description}
                                    </p>

                                    {/* Connector dot between steps on desktop */}
                                    {i < processSteps.length - 1 && (
                                        <div className="hidden lg:block absolute top-1/2 -right-[10px] w-1.5 h-1.5 rounded-full bg-[#27272a] -translate-y-1/2" />
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
