import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import { PlaygroundPage } from "@/components/playground/playground-page";

export const metadata = {
  title: "Playground | MCPForge",
};

interface PlaygroundRouteParams {
  params: Promise<{ id: string }>;
}

/**
 * Server component route for /dashboard/servers/[id]/playground.
 *
 * Fetches server data and renders the client-side PlaygroundPage.
 * Auth is enforced by the dashboard layout.
 *
 * The access token is read from the httpOnly cookie server-side and passed
 * as a prop to PlaygroundPage, which uses it for WebSocket authentication.
 * This avoids relying on document.cookie (which can't read httpOnly cookies).
 */
export default async function PlaygroundRoute({ params }: PlaygroundRouteParams) {
  const { id } = await params;

  // Read the access token from the httpOnly cookie (server-side only).
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token")?.value ?? null;

  // Verify server exists and user owns it.
  // Server-side: use API_INTERNAL_URL (Docker internal) to reach the API.
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://api:8000";
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken) {
      headers["Authorization"] = `Bearer ${accessToken}`;
    }
    const res = await fetch(`${baseUrl}/api/v1/servers/${id}`, { headers });
    if (!res.ok) notFound();
    const server = await res.json();

    return (
      <PlaygroundPage
        serverId={server.id}
        serverSlug={server.slug}
        serverName={server.name}
        accessToken={accessToken}
      />
    );
  } catch {
    notFound();
  }
}
