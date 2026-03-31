"use client";

import { useState } from "react";
import { FiMenu, FiX } from "react-icons/fi";

const links = [
    { label: "The Problem", href: "#problem" },
    { label: "What It Does", href: "#solution" },
    { label: "Demo", href: "#demo" },
];

export default function Navbar({ onRequestAccess }: { onRequestAccess: () => void }) {
    const [open, setOpen] = useState(false);

    return (
        <header className="fixed top-0 w-full z-50 bg-[#09090b]/80 backdrop-blur-md border-b border-[#27272a]">
            <nav className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
                <span className="text-sm font-semibold tracking-tight text-white">TaxSync</span>

                <div className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
                    {links.map((l) => (
                        <a
                            key={l.href}
                            href={l.href}
                            className="text-sm text-[#71717a] hover:text-white transition-colors"
                        >
                            {l.label}
                        </a>
                    ))}
                </div>

                <div className="hidden md:flex items-center">
                    <button
                        onClick={onRequestAccess}
                        className="px-4 py-1.5 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors cursor-pointer"
                    >
                        Start Beta Trial
                    </button>
                </div>

                <button
                    onClick={() => setOpen(!open)}
                    className="md:hidden text-[#a1a1aa] hover:text-white cursor-pointer"
                    aria-label="Toggle menu"
                >
                    {open ? <FiX className="w-5 h-5" /> : <FiMenu className="w-5 h-5" />}
                </button>
            </nav>

            {open && (
                <div className="md:hidden bg-[#09090b]/95 backdrop-blur-md border-t border-[#27272a]">
                    <div className="px-6 py-4 flex flex-col gap-3">
                        {links.map((l) => (
                            <a
                                key={l.href}
                                href={l.href}
                                onClick={() => setOpen(false)}
                                className="text-sm text-[#71717a] hover:text-white transition-colors py-1.5"
                            >
                                {l.label}
                            </a>
                        ))}
                        <div className="pt-3 border-t border-[#27272a]">
                            <button
                                onClick={() => { onRequestAccess(); setOpen(false); }}
                                className="w-full px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors cursor-pointer"
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
