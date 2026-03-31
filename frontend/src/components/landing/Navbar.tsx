"use client";

import { useState, useCallback } from "react";
import { FiMenu, FiX } from "react-icons/fi";

const links = [
    { label: "The Problem", href: "#problem" },
    { label: "What It Does", href: "#solution" },
    { label: "Demo", href: "#demo" },
];

export default function Navbar({ onRequestAccess }: { onRequestAccess: () => void }) {
    const [open, setOpen] = useState(false);

    const handleToggle = useCallback(() => {
        setOpen((prev) => !prev);
    }, []);

    const handleClose = useCallback(() => {
        setOpen(false);
    }, []);

    const handleMobileCTA = useCallback(() => {
        onRequestAccess();
        setOpen(false);
    }, [onRequestAccess]);

    return (
        <header className="fixed top-0 w-full z-50 bg-[#09090b]/80 backdrop-blur-md border-b border-[#27272a]">
            <nav className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
                {/* Brand */}
                <span className="text-sm font-semibold tracking-tight text-white select-none">
                    TaxSync
                </span>

                {/* Desktop nav links - centered */}
                <div className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
                    {links.map((l) => (
                        <a
                            key={l.href}
                            href={l.href}
                            className="text-sm text-[#71717a] hover:text-white transition-colors duration-200"
                        >
                            {l.label}
                        </a>
                    ))}
                </div>

                {/* Desktop CTA - border style, not filled */}
                <div className="hidden md:flex items-center">
                    <button
                        onClick={onRequestAccess}
                        className="px-4 py-1.5 text-sm font-medium text-[#a1a1aa] hover:text-white border border-[#27272a] hover:border-[#3f3f46] rounded-lg transition-colors duration-200 cursor-pointer"
                    >
                        Start Beta Trial
                    </button>
                </div>

                {/* Mobile hamburger */}
                <button
                    onClick={handleToggle}
                    className="md:hidden text-[#a1a1aa] hover:text-white transition-colors duration-200 cursor-pointer"
                    aria-label="Toggle menu"
                >
                    {open ? <FiX className="w-5 h-5" /> : <FiMenu className="w-5 h-5" />}
                </button>
            </nav>

            {/* Mobile drawer */}
            {open && (
                <div className="md:hidden bg-[#09090b]/95 backdrop-blur-md border-t border-[#27272a]">
                    <div className="px-6 py-4 flex flex-col gap-1">
                        {links.map((l) => (
                            <a
                                key={l.href}
                                href={l.href}
                                onClick={handleClose}
                                className="text-sm text-[#71717a] hover:text-white transition-colors duration-200 py-2"
                            >
                                {l.label}
                            </a>
                        ))}
                        <div className="pt-3 mt-2 border-t border-[#27272a]">
                            <button
                                onClick={handleMobileCTA}
                                className="w-full px-4 py-2 text-sm font-medium text-[#a1a1aa] hover:text-white border border-[#27272a] hover:border-[#3f3f46] rounded-lg transition-colors duration-200 cursor-pointer"
                            >
                                Start Beta Trial
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </header>
    );
}
