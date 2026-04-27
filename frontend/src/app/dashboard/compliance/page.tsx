"use client";

import Link from "next/link";
import { FiBriefcase, FiFileText } from "react-icons/fi";

/**
 * Compliance section landing page.
 *
 * Plan 09-06 implements the foundation (clients + onboarding + team). The
 * notice-centric surfaces (compliance dashboard, notice table, detail page,
 * audit log viewer, on-demand reports) land in Plan 09-07 (Wave 6). For now
 * this index page links to the operational entry points that exist today.
 *
 * Render: production-grade landing with clear navigation, NOT a placeholder
 * stub. The "View notices" tile is rendered as a "Coming in Plan 09-07"
 * empty state per UI-SPEC discipline.
 */
export default function ComplianceIndexPage() {
    return (
        <div className="px-6 py-8 max-w-5xl mx-auto">
            <div className="mb-6">
                <h1 className="text-lg font-semibold text-white mb-1">
                    Compliance
                </h1>
                <p className="text-[#71717a] text-sm">
                    Manage clients, notices, and compliance workflows.
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Link
                    href="/dashboard/compliance/clients"
                    className="
                        block p-6 rounded-md
                        bg-[#111113] border border-[#27272a]
                        hover:border-[#3f3f46] hover:bg-[#18181b]/30 transition-colors
                        focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/40
                    "
                >
                    <FiBriefcase className="w-6 h-6 text-[#3b82f6] mb-3" />
                    <h2 className="text-sm font-semibold text-white mb-1">
                        Clients
                    </h2>
                    <p className="text-[13px] text-[#71717a]">
                        Onboard new clients, manage registrations, and assign
                        team members.
                    </p>
                </Link>

                <div
                    className="
                        block p-6 rounded-md
                        bg-[#111113] border border-[#27272a]
                        opacity-60 cursor-not-allowed
                    "
                    aria-disabled="true"
                >
                    <FiFileText className="w-6 h-6 text-[#71717a] mb-3" />
                    <h2 className="text-sm font-semibold text-[#a1a1aa] mb-1">
                        Notices
                    </h2>
                    <p className="text-[13px] text-[#71717a] mb-2">
                        Upload notices, track their workflow, and run bulk
                        actions.
                    </p>
                    <span className="text-[11px] uppercase tracking-wider text-[#52525b]">
                        Coming in Plan 09-07
                    </span>
                </div>
            </div>
        </div>
    );
}
