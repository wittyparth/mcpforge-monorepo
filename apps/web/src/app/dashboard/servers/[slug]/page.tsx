"use client";

import { use } from "react";
import Link from "next/link";
import { ArrowLeft, Construction } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ServerDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = use(params);

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/dashboard/servers"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to servers
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>{slug}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Construction className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">Coming soon</h3>
            <p className="mt-2 max-w-md text-sm text-muted-foreground">
              The server detail page with playground, analytics, and AI
              description engine is under active development. Check back soon!
            </p>
            <div className="mt-6 grid grid-cols-2 gap-4 text-left text-sm">
              <div className="rounded-lg border p-3">
                <div className="font-medium">Playground</div>
                <div className="text-muted-foreground">Test tool calls</div>
              </div>
              <div className="rounded-lg border p-3">
                <div className="font-medium">Description Editor</div>
                <div className="text-muted-foreground">
                  Edit AI-enhanced descriptions
                </div>
              </div>
              <div className="rounded-lg border p-3">
                <div className="font-medium">Analytics</div>
                <div className="text-muted-foreground">Usage metrics</div>
              </div>
              <div className="rounded-lg border p-3">
                <div className="font-medium">Settings</div>
                <div className="text-muted-foreground">Configuration</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
