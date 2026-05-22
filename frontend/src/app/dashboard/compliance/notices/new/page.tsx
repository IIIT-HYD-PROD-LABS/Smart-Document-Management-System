"use client";

import Link from "next/link";
import { FiArrowLeft } from "react-icons/fi";
import { useCurrentClient } from "@/stores/currentClientStore";
import { ExtractionPreviewForm } from "@/components/compliance/ExtractionPreviewForm";

/**
 * Notice creation — Phase 17 D-26 upload-first.
 *
 * The form is now an orchestrator around `ExtractionPreviewForm`. Tenants
 * drop a notice PDF and the AI extractor (Phase 16 BYOK) pre-fills the
 * canonical fields with per-field confidence badges. The "Fill manually"
 * link in the dropzone keeps the v1.0 typed-entry path one click away.
 */

export default function NewNoticePage() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);

    if (activeClientId === null) {
        return (
            <div className="px-6 py-8 max-w-3xl mx-auto">
                <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                    Upload notice
                </h1>
                <p className="text-[13px] text-[var(--text-muted)]">
                    Select a client from the switcher first, then return here to
                    upload a notice.
                </p>
            </div>
        );
    }

    return (
        <div className="px-6 py-8 max-w-3xl mx-auto">
            <Link
                href="/dashboard/compliance"
                className="inline-flex items-center gap-1.5 text-[12px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-4 focus:outline-none focus:ring-2 focus:ring-[var(--accent-edge)] rounded px-1 cursor-pointer transition-colors"
            >
                <FiArrowLeft className="w-3.5 h-3.5" />
                Back to dashboard
            </Link>

            <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                New notice
            </h1>
            <p className="text-[13px] text-[var(--text-muted)] mb-6">
                Drop the notice file to let AI pre-fill the form, or skip to
                manual entry.
            </p>

            <ExtractionPreviewForm activeClientId={activeClientId} />
        </div>
    );
}
