"use client";

/**
 * Remove legacy workspace payloads written by older CareerFit builds.
 * Current workspace state is memory-only and disappears when its protected
 * layout unmounts.
 */
export function clearWorkspaceCaches() {
  try {
    for (let index = sessionStorage.length - 1; index >= 0; index -= 1) {
      const key = sessionStorage.key(index);
      if (key?.startsWith("careerfit:workspace:")) sessionStorage.removeItem(key);
    }
  } catch {
    // Session storage is optional and may be unavailable in hardened browsers.
  }
}
