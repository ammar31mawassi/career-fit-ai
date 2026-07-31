"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  BriefcaseBusiness,
  BellOff,
  ChevronDown,
  Clock3,
  Compass,
  LockKeyhole,
  Mail,
  Power,
  Radar,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Target,
  UsersRound
} from "lucide-react";
import { useAppData } from "@/components/AppDataProvider";
import { CareerInterestPicker } from "@/components/CareerInterestPicker";
import { RecommendedMatches } from "@/components/home/RecommendedMatches";
import {
  getNotificationPreference,
  getRecommendations,
  refreshRecommendations,
  saveNotificationPreference,
  saveProfilePreferences,
  toJobSummary,
  type JobRecommendation,
  type NotificationPreference
} from "@/lib/api";

export function DiscoverClient() {
  const { profile, profileLoading, dataError, setProfile, setJobs } = useAppData();
  const [persistedInterests, setPersistedInterests] = useState<string[]>([]);
  const [careerInterests, setCareerInterests] = useState<string[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [recommendations, setRecommendations] = useState<JobRecommendation[]>([]);
  const [notificationPreference, setNotificationPreference] = useState<NotificationPreference | null>(null);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const [loadingNotifications, setLoadingNotifications] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const skipNextAutomaticLoad = useRef(false);
  const draftDirty = !sameInterests(careerInterests, persistedInterests);

  useEffect(() => {
    if (!profile) return;
    setPersistedInterests(profile.career_interests);
    setCareerInterests(profile.career_interests);
    setEnabled(profile.recommendations_enabled);
  }, [profile?.id, profile?.career_interests, profile?.recommendations_enabled]);

  useEffect(() => {
    if (!enabled) {
      setRecommendations([]);
      setLoadingMatches(false);
      return;
    }
    if (skipNextAutomaticLoad.current) {
      skipNextAutomaticLoad.current = false;
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoadingMatches(true);
    void getRecommendations(30, controller.signal)
      .then((items) => { if (active) setRecommendations(items); })
      .catch((caught) => {
        if (active && !controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Could not load discovery matches.");
        }
      })
      .finally(() => { if (active) setLoadingMatches(false); });
    return () => {
      active = false;
      controller.abort();
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setNotificationPreference(null);
      return;
    }
    const controller = new AbortController();
    setLoadingNotifications(true);
    void getNotificationPreference(controller.signal)
      .then(setNotificationPreference)
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : "Could not load email alert settings.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingNotifications(false);
      });
    return () => controller.abort();
  }, [enabled]);

  const sourceCount = useMemo(
    () => new Set(recommendations.map((item) => item.source_name)).size,
    [recommendations]
  );
  const profileReady = profile?.status === "ready" && profile.onboarding_completed;

  async function allowDiscovery() {
    if (!profileReady) {
      setError("Complete and confirm your profile before turning on discovery.");
      return;
    }
    if (!careerInterests.length) {
      setError("Choose at least one career field so discovery knows where to look.");
      return;
    }
    setSaving(true);
    setLoadingMatches(true);
    setError("");
    setMessage("");
    try {
      const updated = await saveProfilePreferences(careerInterests, true);
      skipNextAutomaticLoad.current = true;
      setProfile(updated);
      setPersistedInterests(updated.career_interests);
      setCareerInterests(updated.career_interests);
      setEnabled(true);
    } catch (caught) {
      setEnabled(false);
      setError(caught instanceof Error ? caught.message : "Could not enable discovery.");
      setSaving(false);
      setLoadingMatches(false);
      return;
    }
    try {
      const items = await refreshRecommendations();
      setRecommendations(items);
      setMessage(items.length
        ? `Discovery is on. ${items.length} matching ${items.length === 1 ? "role is" : "roles are"} ready.`
        : "Discovery is on. We are watching new and shared roles for you.");
    } catch (caught) {
      setMessage("Discovery is on and will continue checking new roles.");
      setError(caught instanceof Error ? `The first catalog check could not finish: ${caught.message}` : "The first catalog check could not finish.");
    } finally {
      setSaving(false);
      setLoadingMatches(false);
    }
  }

  async function pauseDiscovery() {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      if (notificationPreference?.email_enabled) {
        const preference = await saveNotificationPreference(false);
        setNotificationPreference(preference);
      }
      const updated = await saveProfilePreferences(persistedInterests, false);
      setProfile(updated);
      setPersistedInterests(updated.career_interests);
      setCareerInterests(updated.career_interests);
      setEnabled(false);
      setRecommendations([]);
      setMessage("Discovery is paused. Your saved opportunities stay unchanged.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not pause discovery.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleEmailAlerts() {
    if (!notificationPreference?.eligible || !notificationPreference.delivery_available) return;
    setLoadingNotifications(true);
    setError("");
    setMessage("");
    try {
      const updated = await saveNotificationPreference(!notificationPreference.email_enabled);
      setNotificationPreference(updated);
      setMessage(updated.email_enabled
        ? "Email alerts are on for eligible higher-confidence matches."
        : "Email alerts are off. In-app discovery remains active.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update email alerts.");
    } finally {
      setLoadingNotifications(false);
    }
  }

  async function saveDirection() {
    if (!careerInterests.length) {
      setError("Keep at least one career field selected while discovery is on.");
      return;
    }
    setSaving(true);
    setLoadingMatches(true);
    setError("");
    setMessage("");
    try {
      const updated = await saveProfilePreferences(careerInterests, true);
      setProfile(updated);
      setPersistedInterests(updated.career_interests);
      setCareerInterests(updated.career_interests);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update discovery.");
      setSaving(false);
      setLoadingMatches(false);
      return;
    }
    try {
      const items = await refreshRecommendations();
      setRecommendations(items);
      setMessage("Discovery direction saved and existing roles checked again.");
    } catch (caught) {
      setMessage("Discovery direction saved. The next scheduled run will use it.");
      setError(caught instanceof Error ? `The immediate catalog check failed: ${caught.message}` : "The immediate catalog check failed.");
    } finally {
      setSaving(false);
      setLoadingMatches(false);
    }
  }

  async function saveDirectionOnly() {
    if (!careerInterests.length) {
      setError("Choose at least one career field to save your direction.");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const updated = await saveProfilePreferences(careerInterests, false);
      setProfile(updated);
      setPersistedInterests(updated.career_interests);
      setCareerInterests(updated.career_interests);
      setMessage("Career direction saved. Discovery remains off.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save your career direction.");
    } finally {
      setSaving(false);
    }
  }

  function discardDirectionDraft() {
    setCareerInterests(persistedInterests);
    setError("");
    setMessage("Unsaved direction changes discarded.");
  }

  async function reloadMatches() {
    if (!enabled) return;
    setLoadingMatches(true);
    setError("");
    setMessage("");
    try {
      const items = await refreshRecommendations();
      setRecommendations(items);
      setMessage("Discovery checked the current job catalog again.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not refresh discovery.");
    } finally {
      setLoadingMatches(false);
    }
  }

  return (
    <div className="discover-page">
      <header className={`page-heading discover-hero ${enabled ? "is-enabled" : "is-disabled"}`}>
        <div className="discover-hero-copy">
          <span className="eyebrow"><Compass size={14} /> Private job discovery</span>
          <h1>Jobs that fit you,<br /><em>before you search.</em></h1>
          <p>CareerFit checks Goozali and community-scanned roles against your approved profile. Your CV, evidence, and score always stay private.</p>
        </div>
      </header>

      {error || dataError ? <div className="notice error" role="alert">{error || dataError}</div> : null}
      {message ? <div className="notice success" role="status">{message}</div> : null}

      {!enabled ? (
        <section className="discover-permission" aria-labelledby="discover-permission-title">
          <div className="discover-permission-copy">
            <span className="discover-orbit" aria-hidden><Radar size={32} /></span>
            <span className="section-kicker">Discovery is off</span>
            <h2 id="discover-permission-title">Turn your profile into a private job radar</h2>
            <p>Choose the work you want. CareerFit will compare your approved evidence with one combined catalog and only show roles that clear the matching threshold.</p>
            <div className="discover-principles">
              <span><ShieldCheck size={17} /><b>Private matching</b><small>Only you see your evidence and score.</small></span>
              <span><UsersRound size={17} /><b>One useful feed</b><small>Goozali and shared scans stay together.</small></span>
              <span><LockKeyhole size={17} /><b>You decide</b><small>Save, dismiss, or pause at any time.</small></span>
            </div>
          </div>
          <div className="discover-permission-action">
            <div className="section-heading compact-heading">
              <div>
                <span className="section-kicker">Choose your direction</span>
                <h2>What should we watch?</h2>
                <p>These fields narrow discovery. They never increase your match score.</p>
              </div>
              <span className="review-count">{careerInterests.length} selected</span>
            </div>
            <CareerInterestPicker disabled={saving || profileLoading} onChange={setCareerInterests} selected={careerInterests} />
            {!profileReady && !profileLoading ? (
              <div className="discover-profile-warning"><span>Your profile must be ready first.</span><Link href="/profile">Complete profile</Link></div>
            ) : null}
            <div className="form-actions">
              <button
                className="button"
                disabled={saving || profileLoading || !careerInterests.length || !draftDirty}
                onClick={() => void saveDirectionOnly()}
                type="button"
              >
                <Save size={16} /> Save direction only
              </button>
              <button
                className="button primary allow-discovery-button"
                disabled={saving || profileLoading || !profileReady || !careerInterests.length}
                onClick={() => void allowDiscovery()}
                type="button"
              >
                <Sparkles size={17} /> {saving ? "Saving…" : "Allow job discovery"}
              </button>
            </div>
            <small className="consent-footnote">By allowing discovery, you consent to private automated matching. You can turn it off here at any time.</small>
          </div>
        </section>
      ) : (
        <>
          <section className="discover-status-strip" aria-label="Discovery status">
            <div className="discovery-live">
              <span aria-hidden />
              <div><small>Discovery status</small><strong>Actively watching</strong></div>
            </div>
            <div className="discover-status-facts">
              <span><Target size={15} aria-hidden /><span><small>Direction</small><strong>{persistedInterests.length} {persistedInterests.length === 1 ? "field" : "fields"}</strong></span></span>
              <span><BriefcaseBusiness size={15} aria-hidden /><span><small>Current feed</small><strong>{recommendations.length ? `${recommendations.length} ${recommendations.length === 1 ? "match" : "matches"} · ${sourceCount} ${sourceCount === 1 ? "source" : "sources"}` : "Watching for a match"}</strong></span></span>
              <span><Clock3 size={15} aria-hidden /><span><small>Next checks</small><strong>Hourly + shared scans</strong></span></span>
            </div>
            <div className="discover-status-actions">
              <button className="button quiet" disabled={loadingMatches} onClick={() => void reloadMatches()} type="button">
                <RefreshCw className={loadingMatches ? "spin" : ""} size={15} /> {loadingMatches ? "Checking…" : "Check now"}
              </button>
              <button className="button quiet discover-pause" disabled={saving} onClick={() => void pauseDiscovery()} type="button">
                <Power size={15} /> Pause
              </button>
            </div>
          </section>

          <RecommendedMatches
            items={recommendations}
            loading={loadingMatches}
            onItemsChange={setRecommendations}
            onRefresh={() => void reloadMatches()}
            onSaved={(job) => {
              const summary = toJobSummary(job);
              setJobs((current) => [summary, ...current.filter((item) => item.id !== job.id)]);
              setMessage("Role saved to Opportunities.");
            }}
            showEmpty
          />

          <section className="discover-settings-grid" aria-label="Discovery settings">
            <details className="panel discover-direction-panel">
              <summary className="discover-settings-summary">
                <span className="discover-settings-icon"><Target size={18} aria-hidden /></span>
                <span>
                  <small>Discovery settings</small>
                  <strong>Change the fields we watch</strong>
                  <span>{persistedInterests.length} active{draftDirty ? " · unsaved changes" : ""}</span>
                </span>
                <ChevronDown className="discover-settings-chevron" size={18} aria-hidden />
              </summary>
              <div className="discover-settings-body">
                <div className="section-heading compact-heading">
                  <div><span className="section-kicker">Your direction</span><h2>Which roles should enter your feed?</h2><p>Career fields are a hard filter. They never inflate a match score.</p></div>
                  <span className="review-count">{careerInterests.length} selected</span>
                </div>
                <CareerInterestPicker disabled={saving} onChange={setCareerInterests} selected={careerInterests} />
                <div className="form-actions">
                  {draftDirty ? <button className="button quiet" disabled={saving} onClick={discardDirectionDraft} type="button">Discard changes</button> : null}
                  <button className="button primary" disabled={saving || !careerInterests.length || !draftDirty} onClick={() => void saveDirection()} type="button"><Save size={15} /> {saving ? "Saving…" : "Save and recheck"}</button>
                </div>
              </div>
            </details>
            <section className="panel notification-preference" aria-labelledby="email-alert-title">
              <div className="section-heading compact-heading">
                <div>
                  <span className="section-kicker">Optional alerts</span>
                  <h2 id="email-alert-title">Higher-confidence match emails</h2>
                  <p>CareerFit uses your verified account email. Messages contain job details and a score, never CV excerpts or raw profile evidence.</p>
                </div>
                {notificationPreference?.email_enabled ? <Mail size={20} aria-hidden /> : <BellOff size={20} aria-hidden />}
              </div>
              {loadingNotifications && !notificationPreference ? <p role="status">Loading email settings…</p> : null}
              {notificationPreference && !notificationPreference.eligible ? (
                <p>Email alerts are currently limited to explicitly enrolled Israel discovery beta accounts. In-app discovery is unaffected.</p>
              ) : null}
              {notificationPreference?.eligible && !notificationPreference.delivery_available ? (
                <p>Email delivery is not configured in this environment. Your matches remain available in CareerFit.</p>
              ) : null}
              {notificationPreference?.eligible && notificationPreference.delivery_available ? (
                <button
                  aria-pressed={notificationPreference.email_enabled}
                  className={`button ${notificationPreference.email_enabled ? "primary" : "quiet"}`}
                  disabled={loadingNotifications}
                  onClick={() => void toggleEmailAlerts()}
                  type="button"
                >
                  {notificationPreference.email_enabled ? <BellOff size={15} /> : <Mail size={15} />}
                  {loadingNotifications
                    ? "Saving…"
                    : notificationPreference.email_enabled
                      ? "Turn email alerts off"
                      : "Turn email alerts on"}
                </button>
              ) : null}
            </section>
          </section>
        </>
      )}
    </div>
  );
}

function sameInterests(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  const expected = new Set(right);
  return left.every((value) => expected.has(value));
}
