import { FileJson, Wand2, Globe } from "lucide-react";

const steps = [
  {
    icon: FileJson,
    title: "1. Paste your OpenAPI spec",
    description:
      "Enter a URL to your OpenAPI 3.0+ spec or upload a JSON/YAML file. We parse it and show you every endpoint with its original descriptions.",
  },
  {
    icon: Wand2,
    title: "2. AI enhances descriptions",
    description:
      "Our engine rewrites every tool name, description, and parameter docs to optimize for LLM selection. Review changes side-by-side and edit if needed.",
  },
  {
    icon: Globe,
    title: "3. Deploy and connect",
    description:
      "Get a permanent, hosted MCP endpoint URL. Add it to Claude Desktop, Cursor, or any MCP client — no redeployment needed when you update descriptions.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-t px-4 py-20 md:py-28">
      <div className="mx-auto max-w-6xl">
        {/* Section header */}
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Three steps to an AI-ready API
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            No CLI, no Docker, no cloud credentials. Just your OpenAPI spec.
          </p>
        </div>

        {/* Steps */}
        <div className="mt-16 grid gap-8 md:grid-cols-3">
          {steps.map((step, index) => (
            <div key={step.title} className="relative text-center">
              {/* Connector line (desktop) */}
              {index < steps.length - 1 && (
                <div className="absolute left-[60%] top-8 hidden h-px w-[80%] bg-border md:block" />
              )}

              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <step.icon className="h-7 w-7" />
              </div>
              <h3 className="mt-6 text-xl font-semibold">{step.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
