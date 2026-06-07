import { Sparkles, Rocket, Monitor, Shield } from "lucide-react";

const features = [
  {
    icon: Sparkles,
    title: "AI Description Engine",
    description:
      "Our AI rewrites every tool name and description to maximize LLM selection accuracy. Based on published research showing 260% better tool selection.",
  },
  {
    icon: Rocket,
    title: "One-Click Deploy",
    description:
      "From spec to deployed MCP endpoint in under 60 seconds. No CLI, no Docker, no cloud config. Just a URL you can add to Claude Desktop.",
  },
  {
    icon: Monitor,
    title: "Browser Playground",
    description:
      "Test your MCP server directly in the browser. Call tools, inspect responses, iterate on descriptions — all without restarting Claude Desktop.",
  },
  {
    icon: Shield,
    title: "Built-in Security",
    description:
      "Automatic SSRF detection, credential encryption, and security scoring before every deployment. Credentials are AES-256-GCM encrypted.",
  },
];

export function Features() {
  return (
    <section id="features" className="border-t bg-muted/30 px-4 py-20 md:py-28">
      <div className="mx-auto max-w-6xl">
        {/* Section header */}
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to ship MCP servers
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            MCPForge handles the entire lifecycle — from spec ingestion to
            deployed, monitored endpoints.
          </p>
        </div>

        {/* Features grid */}
        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-xl border bg-card p-6 transition-colors hover:bg-accent/50"
            >
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <feature.icon className="h-5 w-5" />
              </div>
              <h3 className="font-semibold">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
