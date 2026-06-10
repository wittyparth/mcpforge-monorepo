import type { Page } from "@playwright/test";

export { 
  API_BASE, APP_BASE, testUser, testServer, uniqueId,
  registerUser, loginUser, getMe, logoutUser, refreshTokens,
  loginViaApiAndSetCookies,
  fetchSpec, uploadSpec, selectToolsAndCreateServer,
  startBuild, getBuildStatus, deleteServer, getServer, listServers,
  pauseServer, resumeServer, testConnection, getConnectPanel,
  getTools, updateTool, enhanceTools,
  listCredentials, createCredential, deleteCredential, testCredential,
  listApiKeys, createApiKey, revokeApiKey,
  getTeam, createTeam, getTeamMembers, inviteTeamMember,
  removeTeamMember, updateMemberRole, leaveTeam, getAuditLog,
  getPlans, getSubscription, subscribeToPlan, openBillingPortal, getInvoices,
  getLatestScan, triggerScan, getScanHistory, acknowledgeFinding, getAcknowledgments,
  getGatewaySSE, sendMcpMessage,
  playgroundWsUrl,
  healthCheck, readinessCheck,
} from "./api-helpers";

/**
 * Inject cookies from the browser context into the page.
 * Playwright auto-sends cookies for matching domains, so this
 * is typically only needed after login to ensure the page
 * picks up the session immediately.
 */
export async function syncCookies(page: Page): Promise<void> {
  await page.goto("/");
  await page.waitForLoadState("networkidle");
}
