import "@testing-library/jest-dom/vitest";
import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// Mock Next.js router
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

// Mock next/link
vi.mock("next/link", () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const React = require("react");
  return {
    __esModule: true,
    default: React.forwardRef(function Link(
      { href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown },
      ref: React.Ref<HTMLAnchorElement>,
    ) {
      return React.createElement("a", { href, ref, ...props }, children);
    }),
  };
});

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock window.scrollTo
window.scrollTo = vi.fn();

// Mock element.scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock ResizeObserver (used by Radix UI Dialog/Select)
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
}
