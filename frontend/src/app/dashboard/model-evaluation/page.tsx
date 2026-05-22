"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components";

export const dynamic = "force-dynamic";

export default function LegacyModelEvalRedirect() {
    const router = useRouter();
    useEffect(() => {
        router.replace("/dashboard/admin/model-evaluation");
    }, [router]);
    return (
        <div className="flex items-center justify-center h-64">
            <LoadingSpinner />
        </div>
    );
}
