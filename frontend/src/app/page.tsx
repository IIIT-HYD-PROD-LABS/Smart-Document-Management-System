"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEffect } from "react";
import { motion } from "framer-motion";
import { FiUpload, FiSearch, FiShield, FiZap, FiArrowRight } from "react-icons/fi";

export default function Home() {
    const { user, isLoading } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isLoading && user) router.push("/dashboard");
    }, [user, isLoading, router]);

    const features = [
        {
            icon: <FiZap className="w-6 h-6" />,
            title: "AI Classification",
            desc: "Automatically categorize documents using machine learning — bills, invoices, tax forms, and more.",
        },
        {
            icon: <FiSearch className="w-6 h-6" />,
            title: "Smart Search",
            desc: "Find any document instantly with intelligent full-text search across all your extracted content.",
        },
        {
            icon: <FiUpload className="w-6 h-6" />,
            title: "OCR Extraction",
            desc: "Extract text from scanned PDFs and images with advanced OCR preprocessing pipeline.",
        },
        {
            icon: <FiShield className="w-6 h-6" />,
            title: "Secure Storage",
            desc: "Enterprise-grade security with JWT authentication and encrypted cloud storage.",
        },
    ];

    return (
        <div className="min-h-screen bg-mesh">
            {/* Navbar */}
            <nav className="fixed top-0 w-full z-50 glass">
                <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center">
                            <span className="text-white font-bold text-sm">S</span>
                        </div>
                        <span className="text-lg font-bold gradient-text">SmartDocs</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <button onClick={() => router.push("/login")} className="btn-ghost text-sm">
                            Sign In
                        </button>
                        <button onClick={() => router.push("/register")} className="btn-primary text-sm !px-5 !py-2">
                            Get Started
                        </button>
                    </div>
                </div>
            </nav>

            {/* Hero */}
            <section className="pt-32 pb-20 px-6">
                <div className="max-w-5xl mx-auto text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.7 }}
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-primary-500/30 bg-primary-500/10 text-primary-300 text-sm mb-8">
                            <FiZap className="w-3.5 h-3.5" />
                            Powered by Machine Learning
                        </div>
                        <h1 className="text-5xl md:text-7xl font-extrabold leading-tight mb-6">
                            Document Management,{" "}
                            <span className="gradient-text">Reimagined</span>
                        </h1>
                        <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
                            Upload, classify, and search your documents with AI-powered intelligence.
                            From scanned receipts to tax forms — organized automatically.
                        </p>
                        <div className="flex items-center justify-center gap-4">
                            <button
                                onClick={() => router.push("/register")}
                                className="btn-primary text-base !px-8 !py-3.5 flex items-center gap-2 group"
                            >
                                Start Free
                                <FiArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                            </button>
                            <button onClick={() => router.push("/login")} className="btn-ghost text-base !px-8 !py-3.5">
                                Sign In
                            </button>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Features */}
            <section className="pb-32 px-6">
                <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {features.map((f, i) => (
                        <motion.div
                            key={i}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: 0.2 + i * 0.1, duration: 0.5 }}
                            className="glass-card p-6"
                        >
                            <div className="w-12 h-12 rounded-xl bg-primary-600/20 flex items-center justify-center text-primary-400 mb-4">
                                {f.icon}
                            </div>
                            <h3 className="text-lg font-semibold text-white mb-2">{f.title}</h3>
                            <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
                        </motion.div>
                    ))}
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-slate-800 py-8 px-6">
                <div className="max-w-7xl mx-auto flex items-center justify-between text-sm text-slate-500">
                    <span>© 2025 SmartDocs. Built for IIIT Hyderabad Prod Labs.</span>
                    <span>AI-Powered Document Intelligence</span>
                </div>
            </footer>
        </div>
    );
}
