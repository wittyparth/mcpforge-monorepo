"use client";

import * as React from "react";
import {
  Loader2,
  UploadCloud,
  FileJson,
  X,
  AlertCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useUploadSpec } from "@/hooks/use-spec";
import type { SpecUploadResponse } from "@/types/api";

interface SpecUploadInputProps {
  onSuccess: (spec: SpecUploadResponse) => void;
  onError?: (error: string) => void;
  className?: string;
}

interface FilePreview {
  name: string;
  size: number;
}

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB
const ACCEPTED_TYPES = [".json", ".yaml", ".yml"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Drag-and-drop file upload zone for OpenAPI spec files.
 * Accepts .json, .yaml, .yml up to 5 MB.
 */
const SpecUploadInput = React.forwardRef<HTMLDivElement, SpecUploadInputProps>(
  ({ onSuccess, onError, className }, ref) => {
    const [dragOver, setDragOver] = React.useState(false);
    const [filePreview, setFilePreview] = React.useState<FilePreview | null>(
      null,
    );
    const [fileError, setFileError] = React.useState<string | null>(null);
    const fileInputRef = React.useRef<HTMLInputElement>(null);
    const uploadSpec = useUploadSpec();

    const isLoading = uploadSpec.isPending;

    const validateFile = (file: File): string | null => {
      const ext = "." + file.name.split(".").pop()?.toLowerCase();
      if (!ACCEPTED_TYPES.includes(ext)) {
        return `Invalid file type "${ext}". Accepted: ${ACCEPTED_TYPES.join(", ")}`;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        return `File is too large (${formatFileSize(file.size)}). Maximum is 5 MB.`;
      }
      return null;
    };

    const handleFile = async (file: File) => {
      setFileError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setFileError(validationError);
        return;
      }

      setFilePreview({ name: file.name, size: file.size });

      try {
        const result = await uploadSpec.mutateAsync(file);
        onSuccess(result);
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to upload spec";
        setFileError(message);
        onError?.(message);
      }
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);

      const file = e.dataTransfer.files?.[0];
      if (file) {
        void handleFile(file);
      }
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(true);
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);
    };

    const handleFileInputChange = (
      e: React.ChangeEvent<HTMLInputElement>,
    ) => {
      const file = e.target.files?.[0];
      if (file) {
        void handleFile(file);
      }
      // Reset so the same file can be selected again
      e.target.value = "";
    };

    const clearFile = () => {
      setFilePreview(null);
      setFileError(null);
    };

    return (
      <div ref={ref} className={cn("space-y-4", className)}>
        {/* Drag-drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload OpenAPI spec file"
          className={cn(
            "relative flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-10 text-center transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            dragOver &&
              "scale-[1.01] border-primary bg-primary/5",
            !dragOver &&
              "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-muted/30",
            isLoading && "pointer-events-none opacity-60",
          )}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES.join(",")}
            onChange={handleFileInputChange}
            className="sr-only"
            aria-hidden="true"
          />

          {isLoading ? (
            <Loader2 className="h-12 w-12 animate-spin text-muted-foreground/50" />
          ) : (
            <UploadCloud className="h-12 w-12 text-muted-foreground/50" />
          )}

          {isLoading ? (
            <div className="space-y-1">
              <p className="font-medium text-foreground">Uploading...</p>
              <p className="text-xs text-muted-foreground">
                Parsing your OpenAPI spec
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="font-medium text-foreground">
                Drop your OpenAPI spec here
              </p>
              <p className="text-xs text-muted-foreground">
                JSON or YAML, up to 5MB
              </p>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            className="pointer-events-auto"
          >
            Browse files
          </Button>
        </div>

        {/* File preview */}
        {filePreview && !isLoading && (
          <div className="flex items-center gap-3 rounded-lg border p-3">
            <FileJson className="h-8 w-8 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{filePreview.name}</p>
              <p className="text-xs text-muted-foreground">
                {formatFileSize(filePreview.size)}
              </p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={clearFile}
              aria-label="Clear selected file"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}

        {/* Inline error */}
        {fileError && (
          <div className="flex items-start gap-2 rounded-lg border border-destructive/50 p-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <p>{fileError}</p>
          </div>
        )}
      </div>
    );
  },
);
SpecUploadInput.displayName = "SpecUploadInput";

export { SpecUploadInput };
export type { SpecUploadInputProps };
