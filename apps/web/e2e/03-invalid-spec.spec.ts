import { test, expect } from "@playwright/test";
import { mockAuthMe, mockSpecFetch422 } from "./helpers";

test.describe("Invalid spec handling", () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthMe(page);
  });

  test("shows client-side validation error for HTTP URL", async ({ page }) => {
    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    await page.getByLabel("OpenAPI Spec URL").fill("http://insecure.example.com/spec.json");
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    await expect(page.getByText("Only HTTPS URLs are allowed")).toBeVisible();
  });

  test("shows API error when spec fetch returns 422", async ({ page }) => {
    await mockSpecFetch422(page);

    await page.goto("/dashboard/servers/new");
    await expect(page.getByText("Import OpenAPI Spec")).toBeVisible();

    await page.getByLabel("OpenAPI Spec URL").fill("https://example.com/invalid-spec.json");
    await page.getByRole("button", { name: "Fetch Spec" }).click();

    await expect(
      page.getByText("Invalid spec: missing openapi field").first(),
    ).toBeVisible({ timeout: 10000 });
  });
});
