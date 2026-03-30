import Link from "next/link";

export default function NotFound() {
    return (
        <div className="min-h-screen bg-[#09090b] flex items-center justify-center px-6">
            <div className="max-w-md w-full text-center">
                <div className="text-6xl font-bold text-[#27272a] mb-4">404</div>
                <h2 className="text-lg font-semibold text-white mb-2">Page not found</h2>
                <p className="text-sm text-[#71717a] mb-6">The page you are looking for does not exist or has been moved.</p>
                <Link href="/" className="px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-[#e4e4e7] transition-colors inline-block">
                    Go home
                </Link>
            </div>
        </div>
    );
}
