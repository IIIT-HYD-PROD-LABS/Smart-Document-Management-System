import { redirect } from "next/navigation";

/**
 * /dashboard/email — redirects to /dashboard/email/connect.
 *
 * The email section's natural landing point is the connect page; if the
 * user already has an active credential, ConnectGmailButton renders the
 * connected state with Reconnect/Disconnect controls.
 */
export default function EmailIndexPage() {
    redirect("/dashboard/email/connect");
}
