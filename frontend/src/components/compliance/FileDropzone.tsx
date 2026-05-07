"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { FiUploadCloud } from "react-icons/fi";
import { complianceApi } from "@/lib/api/compliance";

/**
 * FileDropzone — react-dropzone wrapper for notice file upload.
 *
 * Accepts PDF / JPG / PNG only (single file). On successful upload invalidates
 * the notice + activity caches so the parent surfaces (AttachmentList +
 * ActivityTimeline) refetch.
 */

interface Props {
    noticeId: number;
    disabled?: boolean;
}

export function FileDropzone({ noticeId, disabled = false }: Props) {
    const queryClient = useQueryClient();
    const [uploading, setUploading] = useState(false);

    const onDrop = useCallback(
        async (accepted: File[]) => {
            const file = accepted[0];
            if (!file) return;
            setUploading(true);
            try {
                await complianceApi.uploadNoticeFile(noticeId, file);
                toast.success(`Uploaded ${file.name}`);
                queryClient.invalidateQueries({
                    queryKey: ["notice-activity", noticeId],
                });
                queryClient.invalidateQueries({
                    queryKey: ["notice", noticeId],
                });
            } catch (err) {
                const msg =
                    err instanceof Error ? err.message : "Upload failed";
                toast.error(msg);
            } finally {
                setUploading(false);
            }
        },
        [noticeId, queryClient]
    );

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            "application/pdf": [],
            "image/jpeg": [],
            "image/png": [],
        },
        multiple: false,
        disabled: disabled || uploading,
    });

    const stateClass = isDragActive
        ? "border-[var(--accent)] bg-[var(--accent-soft)]"
        : "border-[var(--border-default)] bg-[var(--bg-elevated)] hover:border-[var(--border-emphasis)] hover:bg-[var(--bg-hover)]";

    return (
        <div
            {...getRootProps()}
            className={`rounded-md border-2 border-dashed p-6 text-center cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-edge)] ${stateClass} ${
                disabled || uploading
                    ? "opacity-60 cursor-not-allowed"
                    : ""
            }`}
            role="button"
            aria-label="Upload notice attachment"
        >
            <input {...getInputProps()} />
            <FiUploadCloud
                className="w-6 h-6 text-[var(--text-muted)] mx-auto mb-2"
                aria-hidden="true"
            />
            <p className="text-[13px] text-[var(--text-primary)]">
                {uploading
                    ? "Uploading…"
                    : isDragActive
                      ? "Drop the file to upload"
                      : "Drag a PDF, JPG, or PNG here"}
            </p>
            <p className="text-[11px] text-[var(--text-muted)] mt-1">
                or click to browse · single file, max 50 MB
            </p>
        </div>
    );
}
