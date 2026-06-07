"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  createServerSchema,
  type CreateServerFormData,
} from "@/lib/validators";
import { useCreateServer } from "@/hooks/use-servers";
import Link from "next/link";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export default function NewServerPage() {
  const router = useRouter();
  const createServer = useCreateServer();
  const [slugManuallyEdited, setSlugManuallyEdited] = useState(false);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<CreateServerFormData>({
    resolver: zodResolver(createServerSchema),
    defaultValues: {
      auth_scheme: "none",
    },
  });

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setValue("name", value);
    if (!slugManuallyEdited) {
      setValue("slug", slugify(value));
    }
  };

  const onSubmit = (data: CreateServerFormData) => {
    createServer.mutate(data);
  };

  const authSchemes = [
    { value: "none", label: "None", description: "No authentication required" },
    {
      value: "api_key",
      label: "API Key",
      description: "Header-based API key authentication",
    },
    {
      value: "bearer",
      label: "Bearer Token",
      description: "Bearer token in Authorization header",
    },
    {
      value: "basic",
      label: "Basic Auth",
      description: "Username and password",
    },
    {
      value: "oauth2",
      label: "OAuth 2.0",
      description: "OAuth 2.0 client credentials",
    },
  ] as const;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
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
          <CardTitle>Create MCP Server</CardTitle>
          <CardDescription>
            Enter your API details to create a new MCP server. You&apos;ll be
            able to configure tool selection and AI enhancement after creation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Server name */}
            <div className="space-y-2">
              <Label htmlFor="name">Server name</Label>
              <Input
                id="name"
                placeholder="My API Server"
                {...register("name", {
                  onChange: handleNameChange,
                })}
              />
              {errors.name && (
                <p className="text-sm text-destructive">
                  {errors.name.message}
                </p>
              )}
            </div>

            {/* Slug */}
            <div className="space-y-2">
              <Label htmlFor="slug">Slug</Label>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground shrink-0">
                  mcpforge.io/mcp/v1/
                </span>
                <Input
                  id="slug"
                  placeholder="my-api-server"
                  {...register("slug", {
                    onChange: () => setSlugManuallyEdited(true),
                  })}
                  className="flex-1"
                />
              </div>
              {errors.slug && (
                <p className="text-sm text-destructive">
                  {errors.slug.message}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, and hyphens. 3-50 characters.
              </p>
            </div>

            {/* Base URL */}
            <div className="space-y-2">
              <Label htmlFor="base_url">Base URL</Label>
              <Input
                id="base_url"
                type="url"
                placeholder="https://api.example.com"
                {...register("base_url")}
              />
              {errors.base_url && (
                <p className="text-sm text-destructive">
                  {errors.base_url.message}
                </p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">Description (optional)</Label>
              <Input
                id="description"
                placeholder="A brief description of your API"
                {...register("description")}
              />
              {errors.description && (
                <p className="text-sm text-destructive">
                  {errors.description.message}
                </p>
              )}
            </div>

            {/* Auth scheme */}
            <div className="space-y-3">
              <Label>Authentication scheme</Label>
              <RadioGroup
                defaultValue="none"
                onValueChange={(value) =>
                  setValue(
                    "auth_scheme",
                    value as CreateServerFormData["auth_scheme"],
                  )
                }
                className="grid gap-3"
              >
                {authSchemes.map((scheme) => (
                  <div
                    key={scheme.value}
                    className="flex items-start space-x-3 rounded-md border p-3"
                  >
                    <RadioGroupItem
                      value={scheme.value}
                      id={`auth-${scheme.value}`}
                      className="mt-0.5"
                    />
                    <div className="space-y-0.5">
                      <Label
                        htmlFor={`auth-${scheme.value}`}
                        className="font-medium cursor-pointer"
                      >
                        {scheme.label}
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        {scheme.description}
                      </p>
                    </div>
                  </div>
                ))}
              </RadioGroup>
              {errors.auth_scheme && (
                <p className="text-sm text-destructive">
                  {errors.auth_scheme.message}
                </p>
              )}
            </div>

            {/* Submit */}
            <div className="flex gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.push("/dashboard/servers")}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || createServer.isPending}
              >
                {createServer.isPending ? "Creating..." : "Create Server"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
