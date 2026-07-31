"use client";

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
  loadMoreJobs: () => Promise<TrackedJobSummary[]>;
  refreshAll: () => Promise<void>;
  reportDataError: (message: string) => void;
};

const AppDataContext = createContext<AppData | null>(null);

export function AppDataProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState<Profile | null>(null);
  const [jobs, setJobsState] = useState<TrackedJobSummary[]>([]);
  const [profileLoading, setProfileLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobsNextCursor, setJobsNextCursor] = useState<string | null>(null);
  const [jobsWatermark, setJobsWatermark] = useState<string | null>(null);
  const [dataError, setDataError] = useState("");
  const profileRequestVersion = useRef(0);
  const jobsRequestVersion = useRef(0);

  const setProfile: Dispatch<SetStateAction<Profile | null>> = useCallback((action) => {
    profileRequestVersion.current += 1;
    setProfileLoading(false);
    setProfileState(action);
  }, []);

  const setJobs: Dispatch<SetStateAction<TrackedJobSummary[]>> = useCallback((action) => {
    jobsRequestVersion.current += 1;
    setJobsLoading(false);
    setJobsState(action);
  }, []);

  const refreshProfile = useCallback(async () => {
    const requestVersion = ++profileRequestVersion.current;
    setProfileLoading(true);
    try {
      const data = await getProfile();
      if (requestVersion === profileRequestVersion.current) setProfileState(data);
      return data;
    } finally {
      if (requestVersion === profileRequestVersion.current) setProfileLoading(false);
    }
  }, []);

  const loadMoreJobs = useCallback(async () => {
    if (!jobsNextCursor) return [];
    const requestVersion = ++jobsRequestVersion.current;
    const cursor = jobsNextCursor;
    const watermark = jobsWatermark;
    setJobsLoading(true);
    try {
      const page = await getJobSummaryPage(cursor, 30, watermark);
      if (requestVersion === jobsRequestVersion.current) {
        setJobsState((current) => [
          ...current,
          ...page.items.filter((item) => !current.some((job) => job.id === item.id))
        ]);
        setJobsNextCursor(page.next_cursor);
        setJobsWatermark(page.watermark ?? watermark);
      }
      return page.items;
    } finally {
      if (requestVersion === jobsRequestVersion.current) setJobsLoading(false);
    }
  }, [jobsNextCursor, jobsWatermark]);

  const refreshAll = useCallback(async () => {
    const profileVersion = ++profileRequestVersion.current;
    const jobsVersion = ++jobsRequestVersion.current;
    setDataError("");
    setProfileLoading(true);
    setJobsLoading(true);
    try {
      const data = await getWorkspaceBootstrap();
      if (profileVersion === profileRequestVersion.current) setProfileState(data.profile);
      if (jobsVersion === jobsRequestVersion.current) {
        setJobsState(data.jobs);
        setJobsNextCursor(data.jobs_next_cursor);
        setJobsWatermark(data.jobs_watermark);
      }
    } catch (error) {
      const current = (
        profileVersion === profileRequestVersion.current
        || jobsVersion === jobsRequestVersion.current
      );
      if (!current) return;
      setDataError(error instanceof Error ? error.message : "Could not refresh your workspace.");
      throw error;
    } finally {
      if (profileVersion === profileRequestVersion.current) setProfileLoading(false);
      if (jobsVersion === jobsRequestVersion.current) setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAll().catch(() => {
      // refreshAll owns the user-facing error state.
    });
    return () => {
      profileRequestVersion.current += 1;
      jobsRequestVersion.current += 1;
    };
  }, [refreshAll]);

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
      loadMoreJobs,
      refreshAll,
      reportDataError: setDataError
    }),
    [profile, jobs, profileLoading, jobsLoading, jobsNextCursor, dataError, refreshProfile, loadMoreJobs, refreshAll]
  );

  return <AppDataContext.Provider value={value}>{children}</AppDataContext.Provider>;
}

export function useAppData() {
  const value = useContext(AppDataContext);
  if (!value) throw new Error("useAppData must be used inside AppDataProvider.");
  return value;
}
