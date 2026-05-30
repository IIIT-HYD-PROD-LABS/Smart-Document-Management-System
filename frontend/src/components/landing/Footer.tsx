"use client";

type FooterLink = { label: string; href?: string };

// Only items that resolve to a real destination get an href and become
// interactive; the rest render as plain (non-clickable) labels until built.
const footerLinks: Record<string, FooterLink[]> = {
    Product: [
        { label: "Document Intelligence", href: "#solution" },
        { label: "Compliance Tracking", href: "#solution" },
        { label: "Demo", href: "#demo" },
    ],
    Resources: [
        { label: "The Problem", href: "#problem" },
        { label: "Sign in", href: "/login" },
    ],
    Legal: [
        { label: "Privacy Policy" },
        { label: "Terms of Service" },
        { label: "Security" },
    ],
};

export default function Footer() {
    return (
        <footer className="border-t border-[#27272a] pt-12 pb-8 px-6">
            <div className="max-w-4xl mx-auto">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
                    {/* Brand column */}
                    <div className="col-span-2 md:col-span-1">
                        <span className="text-sm font-semibold text-white tracking-tight">
                            TaxSync
                        </span>
                        <p className="text-xs text-[#a1a1aa] mt-2 leading-relaxed max-w-[200px]">
                            AI-powered document classification and compliance
                            automation for Indian businesses.
                        </p>
                    </div>

                    {/* Link columns */}
                    {Object.entries(footerLinks).map(([category, links]) => (
                        <div key={category}>
                            <h4 className="text-xs font-medium text-[#a1a1aa] mb-3">
                                {category}
                            </h4>
                            <ul className="space-y-2">
                                {links.map((link) => (
                                    <li key={link.label}>
                                        {link.href ? (
                                            <a
                                                href={link.href}
                                                className="text-xs text-[#a1a1aa] hover:text-white transition-colors rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-[#10b981]/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#09090b]"
                                            >
                                                {link.label}
                                            </a>
                                        ) : (
                                            <span className="text-xs text-[#a1a1aa]">
                                                {link.label}
                                            </span>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Bottom bar */}
                <div className="border-t border-[#27272a] pt-6">
                    <span className="text-xs text-[#a1a1aa]">
                        &copy; 2026 TaxSync. IIIT Hyderabad Prod Labs.
                    </span>
                </div>
            </div>
        </footer>
    );
}
