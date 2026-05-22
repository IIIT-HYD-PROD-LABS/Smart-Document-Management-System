"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components";

export const dynamic = "force-dynamic";

export default function LegacyAISettingsRedirect() {
    const router = useRouter();
    useEffect(() => {
        router.replace("/dashboard/admin/ai");
    }, [router]);
    return (
        <div className="flex items-center justify-center h-64">
            <LoadingSpinner />
        </div>
    );
}
