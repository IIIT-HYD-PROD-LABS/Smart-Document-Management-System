"use client";

const footerLinks = {
    Product: ["Document Intelligence", "Compliance Tracking", "Search", "API"],
    Resources: ["Documentation", "Compliance Guide", "Case Study"],
    Legal: ["Privacy Policy", "Terms of Service", "Security"],
};

export default function Footer() {
    return (
        <footer className="border-t border-[#27272a] pt-12 pb-8 px-6">
            <div className="max-w-4xl mx-auto">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-8 mb-12">
                    <div className="col-span-2 md:col-span-1">
                        <span className="text-sm font-semibold text-white tracking-tight">
                            TaxSync
                        </span>
                        <p className="text-xs text-[#52525b] mt-2 leading-relaxed">
                            AI-powered document classification and compliance
                            automation for Indian businesses. A product of IIIT
                            Hyderabad Prod Labs.
                        </p>
                    </div>
                    {Object.entries(footerLinks).map(([category, links]) => (
                        <div key={category}>
                            <h4 className="text-xs font-medium text-[#a1a1aa] mb-3">
                                {category}
                            </h4>
                            <ul className="space-y-2">
                                {links.map((link) => (
                                    <li key={link}>
                                        <span className="text-xs text-[#52525b] hover:text-[#a1a1aa] transition-colors cursor-pointer">
                                            {link}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                <div className="border-t border-[#27272a] pt-6 flex items-center justify-between text-xs text-[#52525b]">
                    <span>
                        &copy; 2026 TaxSync. IIIT Hyderabad Prod Labs.
                    </span>
                    <span />
                </div>
            </div>
        </footer>
    );
}
