/**
 * Google Drive import API client.
 */
import type { AxiosRequestConfig } from "axios";
import api from "@/lib/api";
import { useCurrentClient } from "@/stores/currentClientStore";

function tenantHeaders(): Record<string, string> {
    const state = useCurrentClient.getState();
    if (state.crossClientMode) return { "X-Client-Id": "*" };
    if (state.activeClientId !== null) {
        return { "X-Client-Id": String(state.activeClientId) };
    }
    return {};
}

function withTenant(config?: AxiosRequestConfig): AxiosRequestConfig {
    return {
        ...(config ?? {}),
        headers: {
            ...(config?.headers ?? {}),
            ...tenantHeaders(),
        },
    };
}

export interface DriveFileItem {
    id: string;
    name: string;
    mime_type: string;
    size: number | null;
    modified_time: string | null;
    web_view_link: string | null;
}

export interface DriveImportResult {
    file_id: string;
    name: string;
    status: string;
    document_id?: number | null;
    notice_id?: number | null;
    error?: string | null;
}

export const driveApi = {
    authorize: () =>
        api.get<{ authorize_url: string }>("/drive/oauth/authorize"),

    exchangeSession: (code: string) =>
        api.post<{ access_token: string }>("/drive/session", { code }),

    listFiles: (accessToken: string, q = "") =>
        api.get<{ files: DriveFileItem[]; next_page_token: string | null }>(
            "/drive/files",
            { params: { access_token: accessToken, q } },
        ),

    importFiles: (
        accessToken: string,
        fileIds: string[],
        createNotices = false,
    ) =>
        api.post<{
            results: DriveImportResult[];
            summary: { ok: number; failed: number };
        }>(
            "/drive/import",
            {
                access_token: accessToken,
                file_ids: fileIds,
                create_notices: createNotices,
            },
            withTenant(),
        ),
};

export default driveApi;
