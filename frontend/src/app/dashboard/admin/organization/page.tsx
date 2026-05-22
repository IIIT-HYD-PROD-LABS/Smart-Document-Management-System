"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
    FiBriefcase,
    FiClock,
    FiExternalLink,
    FiInfo,
    FiSliders,
} from "react-icons/fi";

import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";
import type { ClientDetail } from "@/types/compliance";
import { LoadingSpinner } from "@/components";

export const dynamic = "force-dynamic";

const RETENTION_OPTIONS = [
    { value: "90", label: "90 days" },
    { value: "180", label: "180 days" },
    { value: "365", label: "1 year" },
    { value: "1825", label: "5 years (regulatory default)" },
    { value: "0", label: "Indefinite" },
];

function SectionCard({
    title,
    description,
    icon: Icon,
    children,
}: {
    title: string;
    description: string;
    icon: React.ComponentType<{ className?: string }>;
    children: React.ReactNode;
}) {
    return (
        <section className="surface-card p-6">
            <div className="flex items-start gap-3 mb-4">
                <span className="w-8 h-8 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-[var(--accent)]" />
                </span>
                <div className="min-w-0">
                    <h2 className="text-[14px] font-semibold text-[var(--text-primary)]">
                        {title}
                    </h2>
                    <p className="text-[12px] text-[var(--text-muted)] mt-0.5">
                        {description}
                    </p>
                </div>
            </div>
            {children}
        </section>
    );
}

function ComingSoon() {
    return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10.5px] font-medium bg-[var(--bg-hover)] text-[var(--text-muted)] border border-[var(--border-default)]">
            <FiClock className="w-3 h-3" />
            Phase 18
        </span>
    );
}

export default function OrganizationPage() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const crossClient = useCurrentClient((s) => s.crossClientMode);

    const { data: client, isLoading } = useQuery<ClientDetail>({
        queryKey: ["client", activeClientId],
        queryFn: () =>
            complianceApi.getClient(activeClientId as number).then((r) => r.data),
        enabled: Boolean(activeClientId) && !crossClient,
        staleTime: 60_000,
    });

    return (
        <div className="space-y-6">
            <header>
                <p className="microtype mb-2">Admin</p>
                <h1 className="text-[22px] font-semibold tracking-tight text-[var(--text-primary)]">
                    Organization
                </h1>
                <p className="text-[13px] text-[var(--text-muted)] mt-1.5">
                    Tenant identity, retention policy, and operational defaults.
                </p>
            </header>

            <SectionCard
                title="Identity"
                description="Read-only summary, edits live in the Organizations workspace."
                icon={FiBriefcase}
            >
                {crossClient ? (
                    <p className="text-[12.5px] text-[var(--text-muted)]">
                        Cross-client mode is active. Pick a single organization to view its identity.
                    </p>
                ) : isLoading ? (
                    <div className="h-12 flex items-center"><LoadingSpinner /></div>
                ) : !client ? (
                    <p className="text-[12.5px] text-[var(--text-muted)]">
                        No organization selected.
                    </p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3 text-[13px]">
                        <div>
                            <p className="microtype mb-1">Name</p>
                            <p className="text-[var(--text-primary)]">{client.name}</p>
                        </div>
                        {client.industry && (
                            <div>
                                <p className="microtype mb-1">Industry</p>
                                <p className="text-[var(--text-primary)]">{client.industry}</p>
                            </div>
                        )}
                        {(() => {
                            const gstins = client.registrations.filter(
                                (r) => r.type === "GSTIN" && r.is_active,
                            );
                            const pans = client.registrations.filter(
                                (r) => r.type === "PAN" && r.is_active,
                            );
                            return (
                                <>
                                    {gstins.length > 0 && (
                                        <div>
                                            <p className="microtype mb-1">GSTIN</p>
                                            <p className="text-[var(--text-primary)] font-mono text-[12px]">
                                                {gstins[0].value}
                                                {gstins.length > 1 && (
                                                    <span className="text-[var(--text-muted)] ml-1.5">
                                                        +{gstins.length - 1} more
                                                    </span>
                                                )}
                                            </p>
                                        </div>
                                    )}
                                    {pans.length > 0 && (
                                        <div>
                                            <p className="microtype mb-1">PAN</p>
                                            <p className="text-[var(--text-primary)] font-mono text-[12px]">
                                                {pans[0].value}
                                            </p>
                                        </div>
                                    )}
                                </>
                            );
                        })()}
                    </div>
                )}
                <div className="mt-4 pt-4 border-t border-[var(--border-subtle)]">
                    <Link
                        href={
                            client?.id
                                ? `/dashboard/compliance/clients/${client.id}`
                                : "/dashboard/compliance/clients"
                        }
                        className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--accent)] hover:text-[var(--accent-strong)] transition-colors"
                    >
                        Manage in Organizations
                        <FiExternalLink className="w-3.5 h-3.5" />
                    </Link>
                </div>
            </SectionCard>

            <SectionCard
                title="Data retention"
                description="How long uploaded documents and audit entries are kept."
                icon={FiClock}
            >
                <div className="flex items-center justify-between">
                    <label
                        htmlFor="retention-select"
                        className="text-[13px] text-[var(--text-primary)]"
                    >
                        Document retention period
                    </label>
                    <select
                        id="retention-select"
                        defaultValue="1825"
                        disabled
                        className="px-3 h-9 bg-[var(--bg-elevated)] border border-[var(--border-default)] rounded-md text-[13px] text-[var(--text-disabled)] cursor-not-allowed"
                    >
                        {RETENTION_OPTIONS.map((o) => (
                            <option key={o.value} value={o.value}>
                                {o.label}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="mt-3 flex items-start gap-2">
                    <FiInfo className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0 mt-0.5" />
                    <p className="text-[11.5px] text-[var(--text-muted)]">
                        Audit log entries are immutable (DB trigger blocks delete). Document
                        purge respects compliance holds. <ComingSoon />
                    </p>
                </div>
            </SectionCard>

            <SectionCard
                title="Compliance thresholds"
                description="Tune classifier confidence and review queue triggers."
                icon={FiSliders}
            >
                <div className="flex items-center justify-between">
                    <label
                        htmlFor="confidence-slider"
                        className="text-[13px] text-[var(--text-primary)]"
                    >
                        Review queue confidence threshold
                    </label>
                    <span className="text-[12px] font-mono text-[var(--text-muted)]">
                        0.75
                    </span>
                </div>
                <input
                    id="confidence-slider"
                    type="range"
                    min={0.5}
                    max={0.95}
                    step={0.01}
                    defaultValue={0.75}
                    disabled
                    className="w-full mt-2 cursor-not-allowed opacity-60"
                />
                <p className="text-[11.5px] text-[var(--text-muted)] mt-2">
                    Notices below this score auto-enqueue for human review. <ComingSoon />
                </p>
            </SectionCard>
        </div>
    );
}
