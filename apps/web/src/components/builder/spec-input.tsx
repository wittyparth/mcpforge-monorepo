"use client";

import * as React from "react";
import { Link2, UploadCloud } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { SpecUrlInput } from "@/components/builder/spec-url-input";
import { SpecUploadInput } from "@/components/builder/spec-upload-input";
import { SpecValidationErrors } from "@/components/builder/spec-validation-errors";
import type { SpecUploadResponse } from "@/types/api";

interface SpecInputProps {
  /** Existing spec data, if already configured */
  spec?: SpecUploadResponse | null;
  /** Called when a spec is successfully fetched or uploaded */
  onSuccess: (spec: SpecUploadResponse) => void;
  /** Called when an error occurs during fetch or upload */
  onError?: (error: string) => void;
  className?: string;
}

/**
 * Top-level container for OpenAPI spec input.
 * Provides a tabbed interface: "From URL" or "Upload File".
 */
const SpecInput = React.forwardRef<HTMLDivElement, SpecInputProps>(
  ({ onSuccess, onError, className }, ref) => {
    const [error, setError] = React.useState<string | null>(null);

    const handleError = (message: string) => {
      setError(message);
      onError?.(message);
    };

    const handleSuccess = (spec: SpecUploadResponse) => {
      setError(null);
      onSuccess(spec);
    };

    return (
      <Card ref={ref} className={cn("w-full", className)}>
        <CardHeader>
          <CardTitle>Import OpenAPI Spec</CardTitle>
          <CardDescription>
            Provide an OpenAPI 3.0+ spec. We&apos;ll fetch and parse it for
            you.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs defaultValue="url" className="w-full">
            <TabsList className="w-full">
              <TabsTrigger value="url" className="flex-1 gap-2">
                <Link2 className="h-4 w-4" />
                From URL
              </TabsTrigger>
              <TabsTrigger value="upload" className="flex-1 gap-2">
                <UploadCloud className="h-4 w-4" />
                Upload File
              </TabsTrigger>
            </TabsList>
            <TabsContent value="url" className="pt-4">
              <SpecUrlInput
                onSuccess={handleSuccess}
                onError={handleError}
              />
            </TabsContent>
            <TabsContent value="upload" className="pt-4">
              <SpecUploadInput
                onSuccess={handleSuccess}
                onError={handleError}
              />
            </TabsContent>
          </Tabs>

          {error && (
            <SpecValidationErrors error={error} className="mt-2" />
          )}
        </CardContent>
      </Card>
    );
  },
);
SpecInput.displayName = "SpecInput";

export { SpecInput };
export type { SpecInputProps };
