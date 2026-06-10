"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface JsonViewerProps {
  /** JSON string or object to display */
  value: string | Record<string, unknown> | unknown[];
  /** Whether the viewer is read-only. Defaults to true */
  readOnly?: boolean;
  /** Height of the viewer container. Defaults to "100%" */
  height?: string;
  /** Optional additional CSS classes */
  className?: string;
  /** Called when content changes (only when readOnly=false) */
  onChange?: (value: string) => void;
  /** Line numbers. Defaults to true */
  lineNumbers?: boolean;
}

/**
 * Syntax-highlighted JSON viewer with line numbers.
 *
 * Parses the JSON string and renders it with syntax highlighting spans.
 * No CDN dependencies — renders instantly.
 * Supports optional editing via contentEditable (when readOnly=false).
 */
const JsonViewer = React.forwardRef<HTMLDivElement, JsonViewerProps>(
  (
    {
      value,
      readOnly = true,
      height = "100%",
      className,
      onChange,
      lineNumbers = true,
    },
    ref,
  ) => {
    const stringValue = React.useMemo(() => {
      if (typeof value === "string") return value;
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return String(value);
      }
    }, [value]);

    const editing = false;
    const [editValue, setEditValue] = React.useState(stringValue);
    const scrollRef = React.useRef<HTMLDivElement>(null);
    const lineCountRef = React.useRef<HTMLDivElement>(null);

    React.useEffect(() => {
      if (!editing) {
        setEditValue(stringValue);
      }
    }, [stringValue, editing]);

    // Sync scroll between line numbers and content
    const handleScroll = React.useCallback(() => {
      if (scrollRef.current && lineCountRef.current) {
        lineCountRef.current.scrollTop = scrollRef.current.scrollTop;
      }
    }, []);

    const handleEdit = React.useCallback(
      (e: React.FormEvent<HTMLPreElement>) => {
        const text = (e.target as HTMLElement).textContent ?? "";
        setEditValue(text);
        onChange?.(text);
      },
      [onChange],
    );

    // Syntax highlight a JSON string into HTML spans
    const highlighted = React.useMemo(() => {
      const lines = (editing ? editValue : stringValue).split("\n");
      return lines
        .map((line) => {
          const highlighted = syntaxHighlightLine(line);
          return `<span class="json-line">${highlighted}</span>`;
        })
        .join("\n");
    }, [stringValue, editValue, editing]);

    const lineCount = React.useMemo(
      () => (editing ? editValue : stringValue).split("\n").length,
      [stringValue, editValue, editing],
    );

    return (
      <div
        ref={ref}
        className={cn(
          "overflow-hidden rounded-md border border-border/50 font-mono text-xs leading-relaxed",
          readOnly && "opacity-90",
          className,
        )}
        style={{ height }}
      >
        <div className="flex h-full">
          {/* Line numbers */}
          {lineNumbers && (
            <div
              ref={lineCountRef}
              className="select-none overflow-hidden border-r border-border/30 bg-muted/30 py-3 text-right text-muted-foreground/50"
              style={{ minWidth: "3ch", width: "auto", paddingRight: 8 }}
            >
              {Array.from({ length: lineCount }, (_, i) => (
                <div key={i} className="px-2 text-[10px] leading-relaxed">
                  {i + 1}
                </div>
              ))}
            </div>
          )}

          {/* Content */}
          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="flex-1 overflow-auto"
          >
            {readOnly ? (
              <pre
                className="m-0 p-3 text-foreground whitespace-pre-wrap break-all"
                dangerouslySetInnerHTML={{ __html: highlighted }}
              />
            ) : (
              <pre
                contentEditable
                suppressContentEditableWarning
                className="m-0 p-3 text-foreground whitespace-pre-wrap break-all outline-none"
                onInput={handleEdit}
                dangerouslySetInnerHTML={{ __html: highlighted }}
              />
            )}
          </div>
        </div>
      </div>
    );
  },
);
JsonViewer.displayName = "JsonViewer";

/**
 * Syntax-highlight a single JSON line using regex
 */
function syntaxHighlightLine(line: string): string {
  return line
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    // Keys: "key":
    .replace(
      /^(\s*)"([^"]+)":\s*/,
      '$1<span class="json-key">"$2"</span>: ',
    )
    // Strings: "value"
    .replace(/"([^"]+)"/g, (match, p1) => {
      // Skip already-colored keys
      if (match.includes("json-key")) return match;
      return `<span class="json-string">"${escapeHtml(p1)}"</span>`;
    })
    // Numbers
    .replace(
      /\b(-?\d+\.?\d*)(?![\w.])/g,
      '<span class="json-number">$1</span>',
    )
    // Booleans and null
    .replace(
      /\b(true|false|null)\b/g,
      '<span class="json-boolean">$1</span>',
    )
    // Punctuation (brackets, commas, colons)
    .replace(
      /([{}[\](),])/g,
      '<span class="json-punctuation">$1</span>',
    )
    // Fix: remove re-colonization of colons inside punctuation spans
    .replace(/<\/span><span class="json-punctuation">:<\/span>:/g, ":");
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export { JsonViewer };
