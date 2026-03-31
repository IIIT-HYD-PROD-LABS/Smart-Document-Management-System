"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEffect, useState } from "react";
import { Navbar, Hero, ProblemSection, ProcessFlow, DemoWorkspace, BetaCTA, Footer, EarlyAccessModal } from "@/components/landing";

export default function Home() {
    const { user, isLoading } = useAuth();
    const router = useRouter();
    const [modalOpen, setModalOpen] = useState(false);

    useEffect(() => {
        if (!isLoading && user) router.push("/dashboard");
    }, [user, isLoading, router]);

    const openModal = () => setModalOpen(true);

    return (
        <div className="min-h-screen bg-[#09090b] scroll-smooth">
            <Navbar onRequestAccess={openModal} />
            <Hero onRequestAccess={openModal} />
            <ProblemSection />
            <ProcessFlow />
            <DemoWorkspace />
            <BetaCTA onRequestAccess={openModal} />
            <Footer />
            <EarlyAccessModal open={modalOpen} onClose={() => setModalOpen(false)} />
        </div>
    );
}
