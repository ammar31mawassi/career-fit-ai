"use client";

import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction
} from "react";
import { getJobSummaryPage, getProfile, getWorkspaceBootstrap, type Profile, type TrackedJobSummary } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

type AppData = {
  profile: Profile | null;
  jobs: TrackedJobSummary[];
  profileLoading: boolean;
  jobsLoading: boolean;
  jobsNextCursor: string | null;
  dataError: string;
  setProfile: Dispatch<SetStateAction<Profile | null>>;
  setJobs: Dispatch<SetStateAction<TrackedJobSummary[]>>;
  refreshProfile: () => Promise<Profile>;
  refreshJobs: () => Promise<TrackedJobSummary[]>;
  loadMoreJobs: () => Promise<TrackedJobSummary[]>;
  refreshAll: () => Promise<void>;
  reportDataError: (message: string) => void;
};

const AppDataContext = createContext<AppData | null>(null);
const WORKSPACE_CACHE_PREFIX = "careerfit:workspace:v5:";
const WORKSPACE_CACHE_TTL = 5 * 60 * 1000;
const ONBOARDING_SYNC_KEY = "careerfit:onboarding-syncing";

export function markOnboardingSyncing() {
  try {
    sessionStorage.setItem(ONBOARDING_SYNC_KEY, String(Date.now()));
  } catch {
    // Session storage is optional; the server remains the source of truth.
  }
}

export function clearOnboardingSyncing() {
  try {
    sessionStorage.removeItem(ONBOARDING_SYNC_KEY);
  } catch {
    // Session storage is optional; the marker also expires automatically.
  }
}

function onboardingSyncIsRecent() {
  try {
    const startedAt = Number(sessionStorage.getItem(ONBOARDING_SYNC_KEY) || 0);
    if (startedAt && Date.now() - startedAt < 30_000) return true;
    sessionStorage.removeItem(ONBOARDING_SYNC_KEY);
  } catch {
    // Fall through to the normal server refresh.
  }
  return false;
}

type WorkspaceCache = {
  savedAt: number;
  profile: Profile | null;
  jobs: TrackedJobSummary[];
  jobsNextCursor: string | null;
};

function workspaceCacheKey(userId: string) {
  return `${WORKSPACE_CACHE_PREFIX}${userId}`;
}

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

function readWorkspaceCache(userId: string): WorkspaceCache | null {
  try {
    const key = workspaceCacheKey(userId);
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const cached = JSON.parse(raw) as WorkspaceCache;
    if (!cached.savedAt || Date.now() - cached.savedAt > WORKSPACE_CACHE_TTL) {
      sessionStorage.removeItem(key);
      return null;
    }
    return cached;
  } catch {
    return null;
  }
}

export function AppDataProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const cacheHydrated = useRef(false);
  const [userId, setUserId] = useState<string | null | undefined>(undefined);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [jobs, setJobs] = useState<TrackedJobSummary[]>([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsNextCursor, setJobsNextCursor] = useState<string | null>(null);
  const [dataError, setDataError] = useState("");

  const refreshProfile = useCallback(async () => {
    setProfileLoading(true);
    try {
      const data = await getProfile();
      setProfile(data);
      return data;
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const refreshJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const page = await getJobSummaryPage();
      setJobs(page.items);
      setJobsNextCursor(page.next_cursor);
      return page.items;
    } finally {
      setJobsLoading(false);
    }
  }, []);

  const loadMoreJobs = useCallback(async () => {
    if (!jobsNextCursor) return [];
    setJobsLoading(true);
    try {
      const page = await getJobSummaryPage(jobsNextCursor);
      setJobs((current) => [...current, ...page.items.filter((item) => !current.some((job) => job.id === item.id))]);
      setJobsNextCursor(page.next_cursor);
      return page.items;
    } finally {
      setJobsLoading(false);
    }
  }, [jobsNextCursor]);

  const refreshAll = useCallback(async () => {
    setDataError("");
    setProfileLoading(true);
    setJobsLoading(true);
    try {
      const data = await getWorkspaceBootstrap();
      setProfile(data.profile);
      setJobs(data.jobs);
      setJobsNextCursor(data.jobs_next_cursor);
    } catch (error) {
      setDataError(error instanceof Error ? error.message : "Could not refresh your workspace.");
      throw error;
    } finally {
      setProfileLoading(false);
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    try {
      const supabase = createClient();
      void supabase.auth.getSession().then(({ data }) => {
        if (active) setUserId(data.session?.user.id ?? null);
      });
      const { data } = supabase.auth.onAuthStateChange((_event, session) => {
        if (active) setUserId(session?.user.id ?? null);
      });
      return () => { active = false; data.subscription.unsubscribe(); };
    } catch {
      setUserId(null);
    }
  }, []);

  useEffect(() => {
    if (userId === undefined) return;
    cacheHydrated.current = false;
    setProfile(null);
    setJobs([]);
    setJobsNextCursor(null);
    setDataError("");
    if (!userId) {
      clearWorkspaceCaches();
      setProfileLoading(false);
      setJobsLoading(false);
    } else {
      setProfileLoading(true);
      setJobsLoading(true);
    }
  }, [userId]);

  useEffect(() => {
    if (userId === undefined) return;
    if (pathname === "/login" || !userId) {
      setProfileLoading(false);
      setJobsLoading(false);
      return;
    }

    if (!cacheHydrated.current) {
      cacheHydrated.current = true;
      const cached = readWorkspaceCache(userId);
      if (cached) {
        setProfile(cached.profile);
        setJobs(cached.jobs);
        setJobsNextCursor(cached.jobsNextCursor ?? null);
        setProfileLoading(false);
        setJobsLoading(false);
      }
    }

    if (pathname === "/onboarding" || pathname === "/profile" || pathname === "/discover") {
      void refreshProfile().catch((error) => {
        setDataError(error instanceof Error ? error.message : "Could not load your profile.");
      });
      setJobsLoading(false);
    } else if (pathname === "/") {
      if (onboardingSyncIsRecent()) {
        setProfileLoading(false);
        setJobsLoading(false);
      } else {
        void refreshAll();
      }
    }
  }, [pathname, refreshAll, refreshProfile, userId]);

  useEffect(() => {
    if (pathname === "/login" || profileLoading || !profile) return;
    if (pathname === "/onboarding" && profile.onboarding_completed) {
      router.replace("/");
    } else if (pathname !== "/onboarding" && !profile.onboarding_completed) {
      router.replace("/onboarding");
    }
  }, [pathname, profile, profileLoading, router]);

  useEffect(() => {
    if (pathname === "/login" || !userId || profileLoading || jobsLoading) return;
    try {
      sessionStorage.setItem(
        workspaceCacheKey(userId),
        JSON.stringify({ savedAt: Date.now(), profile, jobs, jobsNextCursor } satisfies WorkspaceCache)
      );
    } catch {
      // A private in-memory session cache is an optimization, never a requirement.
    }
  }, [jobs, jobsLoading, jobsNextCursor, pathname, profile, profileLoading, userId]);

  const value = useMemo(
    () => ({
      profile,
      jobs,
      profileLoading,
      jobsLoading,
      jobsNextCursor,
      dataError,
      setProfile,
      setJobs,
      refreshProfile,
      refreshJobs,
      loadMoreJobs,
      refreshAll,
      reportDataError: setDataError
    }),
    [profile, jobs, profileLoading, jobsLoading, jobsNextCursor, dataError, refreshProfile, refreshJobs, loadMoreJobs, refreshAll]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used inside AppDataProvider.");
  return value;
}
