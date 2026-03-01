"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEffect } from "react";
import { FiArrowRight, FiCpu, FiSearch, FiUpload, FiShield } from "react-icons/fi";

export default function Home() {
    const { user, isLoading } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isLoading && user) router.push("/dashboard");
    }, [user, isLoading, router]);

    return (
        <div className="min-h-screen bg-[#09090b]">
            <nav className="fixed top-0 w-full z-50 bg-[#09090b]/80 backdrop-blur-sm border-b border-[#27272a]">
                <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
                    <span className="text-sm font-semibold tracking-tight text-white">SmartDocs</span>
                    <div className="flex items-center gap-2">
                        <button onClick={() => router.push("/login")} className="px-3 py-1.5 text-sm text-[#a1a1aa] hover:text-white transition-colors cursor-pointer">Sign in</button>
                        <button onClick={() => router.push("/register")} className="px-4 py-1.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors cursor-pointer">Get started</button>
                    </div>
                </div>
            </nav>

            <section className="pt-32 pb-24 px-6">
                <div className="max-w-2xl mx-auto text-center">
                    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[#27272a] text-[#a1a1aa] text-xs mb-8">
                        <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                        AI-powered classification
                    </div>
                    <h1 className="text-4xl md:text-5xl font-semibold leading-tight tracking-tight text-white mb-5">
                        Document management,<br />done right.
                    </h1>
                    <p className="text-base text-[#71717a] max-w-md mx-auto mb-10 leading-relaxed">
                        Upload documents and let ML classify them automatically. OCR extraction, full-text search, and smart categorization.
                    </p>
                    <div className="flex items-center justify-center gap-3">
                        <button onClick={() => router.push("/register")} className="px-6 py-2.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors flex items-center gap-2 cursor-pointer">
                            Start free <FiArrowRight className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => router.push("/login")} className="px-6 py-2.5 text-sm text-[#a1a1aa] hover:text-white border border-[#27272a] rounded-md hover:border-[#3f3f46] transition-colors cursor-pointer">
                            Sign in
                        </button>
                    </div>
                </div>
            </section>

            <section className="pb-32 px-6">
                <div className="max-w-3xl mx-auto">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-px bg-[#27272a] rounded-lg overflow-hidden border border-[#27272a]">
                        {[
                            { icon: FiCpu, title: "AI Classification", desc: "Automatically categorize bills, invoices, tax forms, bank statements, and more." },
                            { icon: FiSearch, title: "Smart Search", desc: "Full-text search across all extracted content. Find any document instantly." },
                            { icon: FiUpload, title: "OCR Extraction", desc: "Extract text from scanned PDFs and images with advanced preprocessing." },
                            { icon: FiShield, title: "Secure Storage", desc: "JWT authentication, rate limiting, and secure file storage." },
                        ].map((f, i) => (
                            <div key={i} className="bg-[#09090b] p-8">
                                <f.icon className="w-5 h-5 text-[#a1a1aa] mb-4" />
                                <h3 className="text-sm font-medium text-white mb-2">{f.title}</h3>
                                <p className="text-sm text-[#71717a] leading-relaxed">{f.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            <footer className="border-t border-[#27272a] py-6 px-6">
                <div className="max-w-5xl mx-auto flex items-center justify-between text-xs text-[#52525b]">
                    <span>SmartDocs. IIIT Hyderabad Prod Labs.</span>
                    <span>2026</span>
                </div>
            </footer>
        </div>
    );
}
