"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEffect } from "react";
import { Navbar, Hero, ProblemSection, ProcessFlow, DemoWorkspace, BetaCTA, Footer } from "@/components/landing";

export default function Home() {
    const { user, isLoading } = useAuth();
    const router = useRouter();

    useEffect(() => {
        if (!isLoading && user) router.push("/dashboard");
    }, [user, isLoading, router]);

    return (
        <div className="min-h-screen bg-[#09090b] scroll-smooth">
            <Navbar />
            <Hero />
            <ProblemSection />
            <ProcessFlow />
            <DemoWorkspace />
            <BetaCTA />
            <Footer />
        </div>
    );
}
