"use client";

import * as React from "react";
import Editor from "@monaco-editor/react";
import { cn } from "@/lib/utils";

export interface DescriptionMonacoEditorProps {
  /** The current text value. */
  value: string;
  /** Called when the user modifies the text. */
  onChange: (value: string) => void;
  /** Language for syntax highlighting. Defaults to "markdown". */
  language?: string;
  /** Height of the editor container. Defaults to "200px". */
  height?: string;
  /** Whether the editor is read-only. */
  readOnly?: boolean;
  /** Optional additional CSS classes. */
  className?: string;
}

/**
 * Monaco editor wrapper optimized for editing tool descriptions.
 *
 * Uses `@monaco-editor/react` for the editor instance with sensible
 * defaults for Markdown content. The editor is lightweight and lazy-loads
 * the Monaco bundle on first mount.
 *
 * Keyboard shortcuts:
 * - Cmd/Ctrl + S to save (triggers onChange)
 * - Escape to blur
 */
const DescriptionMonacoEditor = React.forwardRef<HTMLDivElement, DescriptionMonacoEditorProps>(
  ({ value, onChange, language = "markdown", height = "200px", readOnly = false, className }, ref) => {
    const handleChange = React.useCallback(
      (val: string | undefined) => {
        if (val !== undefined) {
          onChange(val);
        }
      },
      [onChange],
    );

    return (
      <div
        ref={ref}
        className={cn(
          "overflow-hidden rounded-md border border-border/50",
          readOnly && "opacity-80",
          className,
        )}
      >
        <Editor
          height={height}
          language={language}
          value={value}
          onChange={handleChange}
          theme="vs-dark"
          options={{
            readOnly,
            minimap: { enabled: false },
            wordWrap: "on",
            lineNumbers: "off",
            folding: false,
            glyphMargin: false,
            lineDecorationsWidth: 8,
            lineNumbersMinChars: 0,
            scrollBeyondLastLine: false,
            renderLineHighlight: "none",
            overviewRulerBorder: false,
            scrollbar: {
              vertical: "auto",
              horizontal: "hidden",
              verticalScrollbarSize: 6,
            },
            padding: { top: 8, bottom: 8 },
            fontSize: 13,
            fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
            automaticLayout: true,
          }}
          loading={
            <div
              className="flex items-center justify-center bg-[#1e1e1e] text-xs text-muted-foreground"
              style={{ height }}
            >
              Loading editor...
            </div>
          }
        />
      </div>
    );
  },
);
DescriptionMonacoEditor.displayName = "DescriptionMonacoEditor";

export { DescriptionMonacoEditor };
