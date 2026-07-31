/**
 * Resolve an authentication callback destination without allowing a
 * protocol-relative URL, backslash-normalized host, or cross-origin target.
 */
export function safeSameOriginRedirect(requestUrl, requestedNext, fallbackPath = "/") {
  const request = new URL(requestUrl);
  const fallback = new URL(fallbackPath, request.origin);

  if (
    typeof requestedNext !== "string" ||
    !requestedNext.startsWith("/") ||
    requestedNext.startsWith("//") ||
    requestedNext.includes("\\")
  ) {
    return fallback;
  }

  try {
    const target = new URL(requestedNext, request.origin);
    return target.origin === request.origin ? target : fallback;
  } catch {
    return fallback;
  }
}

/**
 * Preserve a requested private workspace destination after login while
 * preventing authentication/API routes and unknown paths from becoming
 * redirect targets.
 */
export function safePostLoginPath(requestUrl, requestedNext, fallbackPath = "/") {
  const fallback = safeSameOriginRedirect(requestUrl, fallbackPath, "/");
  const target = safeSameOriginRedirect(requestUrl, requestedNext, fallback.pathname);
  const allowedPaths = new Set(["/", "/discover", "/profile", "/onboarding"]);
  return allowedPaths.has(target.pathname)
    ? `${target.pathname}${target.search}${target.hash}`
    : `${fallback.pathname}${fallback.search}${fallback.hash}`;
}

export function isAllowedSameOriginRequest(requestUrl, originHeader, configuredSiteUrl) {
  if (!originHeader) return false;
  try {
    const allowedOrigins = new Set([new URL(requestUrl).origin]);
    if (configuredSiteUrl) {
      allowedOrigins.add(new URL(configuredSiteUrl).origin);
    }
    return allowedOrigins.has(new URL(originHeader).origin);
  } catch {
    return false;
  }
}
