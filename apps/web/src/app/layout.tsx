import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "MCPForge — AI-Optimized MCP Servers from OpenAPI Specs",
    template: "%s | MCPForge",
  },
  description:
    "Turn any OpenAPI spec into an AI-optimized MCP server in 60 seconds. Our AI Description Engine rewrites tool descriptions for maximum LLM usability.",
  keywords: [
    "MCP",
    "Model Context Protocol",
    "OpenAPI",
    "AI",
    "LLM",
    "Claude",
    "Cursor",
    "API",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
