import Link from "next/link";

export default function NotFound() {
    return (
        <div className="min-h-screen bg-[var(--bg-page)] flex items-center justify-center px-6">
            <div className="max-w-md w-full text-center">
                <div className="text-6xl font-bold text-[var(--border-emphasis)] mb-4">404</div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-2">Page not found</h2>
                <p className="text-sm text-[var(--text-muted)] mb-6">The page you are looking for does not exist or has been moved.</p>
                <Link href="/" className="px-4 py-2 text-sm font-medium bg-[var(--accent)] text-white rounded-md hover:bg-[var(--accent-strong)] transition-colors inline-block">
                    Go home
                </Link>
            </div>
        </div>
    );
}
