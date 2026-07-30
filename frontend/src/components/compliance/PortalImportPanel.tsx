"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { useDropzone } from "react-dropzone";
import toast from "react-hot-toast";
import { FiFileText, FiLoader, FiUploadCloud } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";
import { useCurrentClient } from "@/stores/currentClientStore";

type PortalKind =
    | "gst_portal"
    | "it_efiling"
    | "mca"
    | "sebi"
    | "rbi"
    | "other";

const PORTALS: { id: PortalKind; label: string; authority: string }[] = [
    { id: "gst_portal", label: "GST portal", authority: "GST" },
    { id: "it_efiling", label: "Income Tax e-filing", authority: "IT" },
    { id: "mca", label: "MCA", authority: "MCA" },
    { id: "sebi", label: "SEBI", authority: "SEBI" },
    { id: "rbi", label: "RBI", authority: "RBI" },
    { id: "other", label: "Other gov portal", authority: "GST" },
];

/**
 * Import PDFs exported from government portals (no scraping).
 * Same OCR → compliance intake pipeline as email attachments.
 */
export default function PortalImportPanel() {
    const activeClientId = useCurrentClient((s) => s.activeClientId);
    const crossClientMode = useCurrentClient((s) => s.crossClientMode);
    const [portal, setPortal] = useState<PortalKind>("gst_portal");
    const [createNotice, setCreateNotice] = useState(true);
    const [busy, setBusy] = useState(false);
    const [lastNoticeId, setLastNoticeId] = useState<number | null>(null);

    const onDrop = useCallback(
        async (accepted: File[]) => {
            const file = accepted[0];
            if (!file) return;
            if (activeClientId == null || crossClientMode) {
                toast.error(
                    "Pick a single organization to import into (not All Clients)",
                );
                return;
            }
            setBusy(true);
            setLastNoticeId(null);
            try {
                const { data } = await complianceApi.importPortalExport(file, {
                    portal,
                    create_notice: createNotice,
                });
                toast.success(
                    data.notice_id
                        ? `Imported. Notice ${data.notice_number} queued for OCR`
                        : `Imported document #${data.document_id} (OCR queued)`,
                );
                if (data.notice_id) setLastNoticeId(data.notice_id);
            } catch (e: unknown) {
                const detail = (
                    e as {
                        response?: {
                            data?: { detail?: string | { message?: string } };
                        };
                    }
                )?.response?.data?.detail;
                const msg =
                    typeof detail === "string"
                        ? detail
                        : typeof detail === "object" && detail?.message
                          ? detail.message
                          : "Portal import failed";
                toast.error(msg);
            } finally {
                setBusy(false);
            }
        },
        [activeClientId, crossClientMode, portal, createNotice],
    );

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        multiple: false,
        disabled: busy || activeClientId == null || crossClientMode,
        accept: {
            "application/pdf": [".pdf"],
            "image/png": [".png"],
            "image/jpeg": [".jpg", ".jpeg"],
            "image/tiff": [".tif", ".tiff"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                [".docx"],
        },
    });

    return (
        <section className="surface-card p-5 space-y-4">
            <div className="flex items-start gap-3">
                <span className="w-9 h-9 rounded-md bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                    <FiFileText className="w-4 h-4 text-[var(--accent)]" />
                </span>
                <div className="min-w-0">
                    <h2 className="text-[14px] font-semibold text-[var(--text-primary)]">
                        Import from gov portal export
                    </h2>
                    <p className="text-[12px] text-[var(--text-muted)] mt-0.5">
                        Download the notice PDF from GST / Income Tax / MCA (or
                        other) portals, then drop it here. We run OCR, fill
                        compliance fields, and surface it on the dashboard,
                        calendar, audit, and reports. We do not log into gov
                        portals for you.
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label className="block text-[12px] text-[var(--text-muted)]">
                    Portal
                    <select
                        value={portal}
                        onChange={(e) => setPortal(e.target.value as PortalKind)}
                        className="mt-1 w-full h-9 px-2 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[13px] text-[var(--text-primary)]"
                    >
                        {PORTALS.map((p) => (
                            <option key={p.id} value={p.id}>
                                {p.label} ({p.authority})
                            </option>
                        ))}
                    </select>
                </label>
                <label className="flex items-center gap-2 mt-6 text-[13px] text-[var(--text-primary)] cursor-pointer">
                    <input
                        type="checkbox"
                        checked={createNotice}
                        onChange={(e) => setCreateNotice(e.target.checked)}
                        className="rounded border-[var(--border-default)]"
                    />
                    Create compliance notice automatically
                </label>
            </div>

            <div
                {...getRootProps()}
                className={`
                    rounded-md border-2 border-dashed p-6 text-center cursor-pointer
                    transition-colors
                    ${
                        isDragActive
                            ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                            : "border-[var(--border-default)] bg-[var(--bg-elevated)] hover:border-[var(--border-emphasis)]"
                    }
                    ${busy || activeClientId == null || crossClientMode ? "opacity-60 cursor-not-allowed" : ""}
                `}
            >
                <input {...getInputProps()} />
                {busy ? (
                    <FiLoader className="w-6 h-6 mx-auto mb-2 text-[var(--accent)] animate-spin" />
                ) : (
                    <FiUploadCloud className="w-6 h-6 mx-auto mb-2 text-[var(--text-muted)]" />
                )}
                <p className="text-[13px] text-[var(--text-primary)]">
                    {busy
                        ? "Uploading & queueing OCR…"
                        : isDragActive
                          ? "Drop the portal PDF"
                          : "Drag portal export here, or click to browse"}
                </p>
                <p className="text-[11px] text-[var(--text-muted)] mt-1">
                    PDF, Word, or image · single file
                </p>
            </div>

            {lastNoticeId != null && (
                <p className="text-[12.5px] text-[var(--text-secondary)]">
                    Notice created.{" "}
                    <Link
                        href={`/dashboard/compliance/notices/${lastNoticeId}`}
                        className="text-[var(--accent)] hover:underline"
                    >
                        Open notice #{lastNoticeId}
                    </Link>{" "}
                    after OCR finishes (usually under a minute).
                </p>
            )}
        </section>
    );
}
