"use client";

import { usePathname } from "next/navigation";
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

export function AppDataProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
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
    if (pathname === "/onboarding") {
      void refreshProfile().catch((error) => {
        setDataError(error instanceof Error ? error.message : "Could not load your profile.");
      });
      setJobsLoading(false);
    } else {
      void refreshAll();
    }
  }, [pathname, refreshAll]);

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
