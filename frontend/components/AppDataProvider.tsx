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
import { getJobs, getProfile, type Profile, type TrackedJob } from "@/lib/api";

type AppData = {
  profile: Profile | null;
  jobs: TrackedJob[];
  profileLoading: boolean;
  jobsLoading: boolean;
  dataError: string;
  setProfile: Dispatch<SetStateAction<Profile | null>>;
  setJobs: Dispatch<SetStateAction<TrackedJob[]>>;
  refreshProfile: () => Promise<Profile>;
  refreshJobs: () => Promise<TrackedJob[]>;
  refreshAll: () => Promise<void>;
};

const AppDataContext = createContext<AppData | null>(null);
const WORKSPACE_CACHE_KEY = "careerfit:workspace:v2";
const WORKSPACE_CACHE_TTL = 5 * 60 * 1000;

type WorkspaceCache = {
  savedAt: number;
  profile: Profile | null;
  jobs: TrackedJob[];
};

function readWorkspaceCache(): WorkspaceCache | null {
  try {
    const raw = sessionStorage.getItem(WORKSPACE_CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw) as WorkspaceCache;
    if (!cached.savedAt || Date.now() - cached.savedAt > WORKSPACE_CACHE_TTL) {
      sessionStorage.removeItem(WORKSPACE_CACHE_KEY);
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
  const started = useRef(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [jobs, setJobs] = useState<TrackedJob[]>([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
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
      const data = await getJobs();
      setJobs(data);
      return data;
    } finally {
      setJobsLoading(false);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setDataError("");
    const results = await Promise.allSettled([refreshProfile(), refreshJobs()]);
    const failure = results.find((result) => result.status === "rejected");
    if (failure?.status === "rejected") {
      setDataError(failure.reason instanceof Error ? failure.reason.message : "Could not refresh your workspace.");
    }
  }, [refreshJobs, refreshProfile]);

  useEffect(() => {
    if (pathname === "/login" || started.current) {
      if (pathname === "/login") {
        setProfileLoading(false);
        setJobsLoading(false);
      }
      return;
    }
    started.current = true;
    const cached = readWorkspaceCache();
    if (cached) {
      setProfile(cached.profile);
      setJobs(cached.jobs);
      setProfileLoading(false);
      setJobsLoading(false);
    }
    if (pathname === "/onboarding") {
      void refreshProfile().catch((error) => {
        setDataError(error instanceof Error ? error.message : "Could not load your profile.");
      });
      setJobsLoading(false);
    } else {
      void refreshAll();
    }
  }, [pathname, refreshAll]);

  useEffect(() => {
    if (pathname === "/login" || profileLoading || !profile) return;
    if (pathname === "/onboarding" && profile.onboarding_completed) {
      router.replace("/");
    } else if (pathname !== "/onboarding" && !profile.onboarding_completed) {
      router.replace("/onboarding");
    }
  }, [pathname, profile, profileLoading, router]);

  useEffect(() => {
    if (pathname === "/login" || profileLoading || jobsLoading) return;
    try {
      sessionStorage.setItem(
        WORKSPACE_CACHE_KEY,
        JSON.stringify({ savedAt: Date.now(), profile, jobs } satisfies WorkspaceCache)
      );
    } catch {
      // A private in-memory session cache is an optimization, never a requirement.
    }
  }, [jobs, jobsLoading, pathname, profile, profileLoading]);

  const value = useMemo(
    () => ({
      profile,
      jobs,
      profileLoading,
      jobsLoading,
      dataError,
      setProfile,
      setJobs,
      refreshProfile,
      refreshJobs,
      refreshAll
    }),
    [profile, jobs, profileLoading, jobsLoading, dataError, refreshProfile, refreshJobs, refreshAll]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used inside AppDataProvider.");
  return value;
}
