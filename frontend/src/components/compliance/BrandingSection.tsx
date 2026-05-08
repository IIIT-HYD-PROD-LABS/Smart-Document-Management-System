"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiImage, FiTrash2, FiUploadCloud } from "react-icons/fi";

import { complianceApi } from "@/lib/api/compliance";
import type { Client } from "@/types/compliance";

interface Props {
    client: Client;
}

const LOGO_MAX_BYTES = 256 * 1024;
const LOGO_ACCEPT = "image/png,image/jpeg,image/webp";
const LOGO_ALLOWED = new Set(["image/png", "image/jpeg", "image/webp"]);

/**
 * Branding section on the client detail page.
 *
 * Layout matches the Registrations card on the same page — `.surface-card`
 * shell, `.microtype` header, two-column on desktop (logo | form). The logo
 * uploader posts immediately on file select; the website + address fields
 * batch into a single PATCH on Save so we don't ping the API per keystroke.
 */
export default function BrandingSection({ client }: Props) {
    const queryClient = useQueryClient();
    const fileInputRef = useRef<HTMLInputElement | null>(null);

    const [website, setWebsite] = useState(client.website ?? "");
    const [address, setAddress] = useState(client.address ?? "");
    const [dragOver, setDragOver] = useState(false);
    const [logoBusy, setLogoBusy] = useState(false);
    const [savingFields, setSavingFields] = useState(false);

    useEffect(() => {
        setWebsite(client.website ?? "");
        setAddress(client.address ?? "");
    }, [client.website, client.address]);

    const dirty =
        website !== (client.website ?? "") ||
        address !== (client.address ?? "");

    const onClientPatched = (next: Client) => {
        queryClient.setQueryData(["client", client.id], (prev: Client | undefined) =>
            prev ? { ...prev, ...next } : next,
        );
        queryClient.invalidateQueries({ queryKey: ["active-client"] });
    };

    const handleFileSelected = async (file: File) => {
        if (!LOGO_ALLOWED.has(file.type)) {
            toast.error("Only PNG, JPEG, or WEBP files are allowed.");
            return;
        }
        if (file.size > LOGO_MAX_BYTES) {
            toast.error(`Logo too large (max ${LOGO_MAX_BYTES / 1024} KB).`);
            return;
        }
        setLogoBusy(true);
        try {
            const r = await complianceApi.uploadClientLogo(client.id, file);
            onClientPatched(r.data);
            toast.success("Logo updated.");
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Logo upload failed.";
            toast.error(msg);
        } finally {
            setLogoBusy(false);
        }
    };

    const handleRemoveLogo = async () => {
        if (!client.logo_url) return;
        setLogoBusy(true);
        try {
            const r = await complianceApi.deleteClientLogo(client.id);
            onClientPatched(r.data);
            toast.success("Logo removed.");
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Logo removal failed.";
            toast.error(msg);
        } finally {
            setLogoBusy(false);
        }
    };

    const handleSaveFields = async () => {
        if (!dirty) return;
        setSavingFields(true);
        try {
            const r = await complianceApi.updateClientBranding(client.id, {
                website: website.trim() || null,
                address: address.trim() || null,
            });
            onClientPatched(r.data);
            toast.success("Saved.");
        } catch (e: unknown) {
            const msg =
                (e as { response?: { data?: { detail?: string } } })?.response
                    ?.data?.detail || "Save failed.";
            toast.error(msg);
        } finally {
            setSavingFields(false);
        }
    };

    return (
        <div className="surface-card p-6">
            <header className="mb-5">
                <h2 className="microtype">Branding</h2>
                <p className="text-[12.5px] text-[var(--text-muted)] mt-1">
                    Show your company logo and details across TaxSync.
                </p>
            </header>

            <div className="grid lg:grid-cols-[160px_1fr] gap-6 items-start">
                {/* Logo uploader */}
                <div className="space-y-2">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept={LOGO_ACCEPT}
                        className="sr-only"
                        onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f) handleFileSelected(f);
                            e.target.value = ""; // allow re-selecting the same file
                        }}
                        aria-label="Upload company logo"
                    />

                    <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        onDragOver={(e) => {
                            e.preventDefault();
                            setDragOver(true);
                        }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={(e) => {
                            e.preventDefault();
                            setDragOver(false);
                            const f = e.dataTransfer.files?.[0];
                            if (f) handleFileSelected(f);
                        }}
                        disabled={logoBusy}
                        className={`
                            relative w-[144px] h-[144px] rounded-md
                            flex items-center justify-center overflow-hidden
                            transition-colors duration-150 cursor-pointer
                            ${
                                client.logo_url
                                    ? "bg-white border border-[var(--border-default)] hover:border-[var(--accent-edge)]"
                                    : dragOver
                                      ? "bg-[var(--accent-soft)] border-2 border-dashed border-[var(--accent)]"
                                      : "bg-[var(--bg-muted)] border-2 border-dashed border-[var(--border-emphasis)] hover:border-[var(--accent-edge)] hover:bg-[var(--bg-hover)]"
                            }
                            ${logoBusy ? "opacity-60 cursor-wait" : ""}
                        `}
                        aria-label={client.logo_url ? "Replace logo" : "Upload logo"}
                    >
                        {client.logo_url ? (
                            <>
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img
                                    src={client.logo_url}
                                    alt={`${client.name} logo`}
                                    className="max-w-full max-h-full object-contain p-3"
                                />
                                <span
                                    className="
                                        absolute inset-0 flex items-center justify-center
                                        bg-[rgba(15,23,42,0.55)] backdrop-blur-[1px]
                                        opacity-0 hover:opacity-100 transition-opacity duration-150
                                        text-white text-[12px] font-medium
                                        gap-1.5
                                    "
                                    aria-hidden
                                >
                                    <FiUploadCloud className="w-3.5 h-3.5" />
                                    Replace
                                </span>
                            </>
                        ) : (
                            <div className="flex flex-col items-center gap-2 px-2 text-center">
                                <FiImage className="w-6 h-6 text-[var(--text-subtle)]" />
                                <span className="text-[11.5px] text-[var(--text-muted)] leading-snug">
                                    Drop logo or click
                                </span>
                            </div>
                        )}
                    </button>

                    <p className="text-[11px] text-[var(--text-subtle)] leading-snug">
                        PNG, JPEG, or WEBP · max 256 KB
                    </p>

                    {client.logo_url && (
                        <button
                            type="button"
                            onClick={handleRemoveLogo}
                            disabled={logoBusy}
                            className="
                                inline-flex items-center gap-1.5 text-[11.5px]
                                text-[var(--text-muted)] hover:text-[var(--danger)]
                                transition-colors duration-150 cursor-pointer
                                disabled:opacity-50 disabled:cursor-not-allowed
                            "
                        >
                            <FiTrash2 className="w-3 h-3" />
                            Remove logo
                        </button>
                    )}
                </div>

                {/* Form fields */}
                <div className="space-y-4">
                    <label className="block">
                        <span className="microtype block mb-1.5">Website</span>
                        <input
                            type="url"
                            value={website}
                            onChange={(e) => setWebsite(e.target.value)}
                            placeholder="https://acme.com"
                            maxLength={255}
                            className="
                                w-full px-3 py-2 rounded-md
                                bg-[var(--bg-page)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                                transition-colors duration-150
                            "
                        />
                    </label>

                    <label className="block">
                        <span className="microtype block mb-1.5">
                            Registered office
                        </span>
                        <textarea
                            value={address}
                            onChange={(e) => setAddress(e.target.value)}
                            rows={3}
                            placeholder="Registered office address"
                            className="
                                w-full px-3 py-2 rounded-md
                                bg-[var(--bg-page)]
                                border border-[var(--border-default)]
                                text-[13px] text-[var(--text-primary)]
                                placeholder:text-[var(--text-disabled)]
                                focus:outline-none focus:border-[var(--accent)]
                                focus:ring-2 focus:ring-[var(--accent-edge)]
                                transition-colors duration-150
                                resize-y
                            "
                        />
                    </label>

                    <div className="flex justify-end gap-2 pt-1">
                        {dirty && (
                            <button
                                type="button"
                                onClick={() => {
                                    setWebsite(client.website ?? "");
                                    setAddress(client.address ?? "");
                                }}
                                disabled={savingFields}
                                className="
                                    px-3 py-1.5 rounded-md text-[12.5px]
                                    text-[var(--text-muted)] hover:text-[var(--text-primary)]
                                    hover:bg-[var(--bg-hover)] cursor-pointer
                                    transition-colors duration-150
                                    disabled:opacity-50 disabled:cursor-not-allowed
                                "
                            >
                                Reset
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={handleSaveFields}
                            disabled={!dirty || savingFields}
                            className="
                                px-4 py-1.5 rounded-md text-[12.5px] font-medium
                                bg-[var(--accent)] text-white
                                hover:bg-[var(--accent-strong)] cursor-pointer
                                transition-colors duration-150
                                disabled:bg-[var(--bg-hover)]
                                disabled:text-[var(--text-disabled)]
                                disabled:cursor-not-allowed
                            "
                        >
                            {savingFields ? "Saving…" : "Save"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
