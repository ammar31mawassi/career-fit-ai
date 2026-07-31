"use client";

import { useMemo, type CSSProperties } from "react";
import { ArrowRight, Check, CircleHelp, FastForward, FileCheck2, ShieldCheck, Waypoints, X } from "lucide-react";
import { CareerDirectionPreview } from "@/components/onboarding/CareerDirectionPreview";
import type { ClarificationQuestion, Profile } from "@/lib/api";

export type FactReviewDecision = "pending" | "confirmed" | "skipped";
export type QuestionReviewDecision = "pending" | "answered" | "skipped" | "no_question";

const QUESTION_PRIORITY: Record<string, number> = {
  years_experience: 100,
  location: 90,
  availability: 80,
  semesters_left: 70,
  project: 60,
  skill: 50,
  about_me: 40
};

export function highestImpactQuestion(questions: ClarificationQuestion[]) {
  return questions
    .filter((question) => question.status === "open")
    .toSorted((left, right) => (QUESTION_PRIORITY[right.field_key] ?? 0) - (QUESTION_PRIORITY[left.field_key] ?? 0))[0] ?? null;
}

export function OnboardingReview({
  profile,
  selectedFactIds,
  factDecision,
  questionDecision,
  questionAnswer,
  error,
  saving,
  onToggleFact,
  onConfirmFacts,
  onSkipFacts,
  onQuestionAnswer,
  onAnswerQuestion,
  onSkipQuestion,
  onFinish
}: {
  profile: Profile;
  selectedFactIds: Set<number>;
  factDecision: FactReviewDecision;
  questionDecision: QuestionReviewDecision;
  questionAnswer: string;
  error: string;
  saving: boolean;
  onToggleFact: (factId: number) => void;
  onConfirmFacts: () => void;
  onSkipFacts: () => void;
  onQuestionAnswer: (value: string) => void;
  onAnswerQuestion: () => void;
  onSkipQuestion: () => void;
  onFinish: () => void;
}) {
  const pendingFacts = useMemo(
    () => profile.facts.filter((fact) => fact.review_status === "pending"),
    [profile.facts]
  );
  const question = highestImpactQuestion(profile.questions);
  const reviewReady = factDecision !== "pending" && questionDecision !== "pending";
  const remaining = Number(factDecision === "pending") + Number(questionDecision === "pending");

  return (
    <main className="onboarding-review-shell">
      <header className="onboarding-review-header">
        <div className="brand">
          <span className="brand-mark"><Waypoints size={18} /></span>
          <span className="brand-copy"><strong>CareerFit</strong><small>Final profile review</small></span>
        </div>
        <div className={`review-gate-status ${reviewReady ? "ready" : ""}`}>
          {reviewReady ? <Check size={14} /> : <ShieldCheck size={14} />}
          {reviewReady ? "Ready to finish" : `${remaining} decision${remaining === 1 ? "" : "s"} left`}
        </div>
      </header>

      <div className="onboarding-review-layout">
        <section className="review-hero">
          <span className="onboarding-logo"><FileCheck2 size={24} /></span>
          <small>Analysis complete · your approval is not</small>
          <h1>Make the profile<br /><em>yours.</em></h1>
          <p>{profile.summary}</p>
          <div className="review-hero-stats">
            <span><strong>{profile.facts.length}</strong> extracted facts</span>
            <span><strong>{profile.career_interests.length}</strong> directions</span>
          </div>
        </section>

        <div className="review-workspace">
          <CareerDirectionPreview facts={profile.facts} interests={profile.career_interests} />

          <section className={`onboarding-fact-review ${factDecision}`} aria-labelledby="fact-review-title">
            <div className="review-section-heading">
              <span aria-hidden><ShieldCheck size={17} /></span>
              <div>
                <small>Required decision 01</small>
                <h2 id="fact-review-title">Confirm the evidence profile</h2>
                <p>Keep accurate facts selected. Unselected facts are rejected when you confirm.</p>
              </div>
              {factDecision !== "pending" ? <strong className="review-decision"><Check size={12} /> {factDecision}</strong> : null}
            </div>
            <div className="onboarding-fact-list">
              {pendingFacts.length ? pendingFacts.map((fact) => {
                const selected = selectedFactIds.has(fact.id);
                const confidence = Math.max(0, Math.min(1, fact.confidence));
                return (
                  <button
                    aria-pressed={selected}
                    className={`onboarding-fact-card ${selected ? "selected" : "rejected"}`}
                    key={fact.id}
                    onClick={() => onToggleFact(fact.id)}
                    type="button"
                  >
                    <span className="fact-review-check" aria-hidden>{selected ? <Check size={13} /> : <X size={13} />}</span>
                    <span className="fact-review-copy">
                      <span dir="auto"><small>{fact.fact_type.replaceAll("_", " ")}</small><strong>{fact.value}</strong></span>
                      <p>{fact.evidence || "Found in the uploaded evidence."}</p>
                      <span className="fact-confidence-copy">
                        <b>{Math.round(confidence * 100)}% extraction confidence</b>
                        <i>{fact.support_count} {fact.support_count === 1 ? "source" : "sources"}</i>
                      </span>
                      <span className="fact-confidence-track" aria-hidden>
                        <i style={{ "--fact-confidence": confidence } as CSSProperties} />
                      </span>
                    </span>
                  </button>
                );
              }) : <div className="review-empty"><Check size={15} /> No pending facts remain.</div>}
            </div>
            <div className="review-decision-actions">
              <span>{selectedFactIds.size} confirmed · {Math.max(0, pendingFacts.length - selectedFactIds.size)} rejected</span>
              <button className="button secondary" onClick={onConfirmFacts} type="button"><Check size={14} /> Confirm these facts</button>
              <button className="review-skip-button" onClick={onSkipFacts} type="button"><FastForward size={13} /> Skip fact review</button>
            </div>
          </section>

          <section className={`onboarding-question-review ${questionDecision}`} aria-labelledby="question-review-title">
            <div className="review-section-heading">
              <span aria-hidden><CircleHelp size={17} /></span>
              <div>
                <small>Required decision 02</small>
                <h2 id="question-review-title">One useful clarification</h2>
                <p>We selected the unanswered detail with the largest likely impact on matching.</p>
              </div>
              {questionDecision !== "pending" ? <strong className="review-decision"><Check size={12} /> {questionDecision.replace("no_question", "complete")}</strong> : null}
            </div>
            {question ? (
              <div className="clarification-card">
                <label htmlFor="onboarding-question-answer">{question.question}</label>
                <textarea
                  id="onboarding-question-answer"
                  onChange={(event) => onQuestionAnswer(event.target.value)}
                  placeholder="Add a short, factual answer…"
                  value={questionAnswer}
                />
                <div className="review-decision-actions">
                  <span>Your answer becomes a user-confirmed profile fact.</span>
                  <button className="button secondary" disabled={!questionAnswer.trim()} onClick={onAnswerQuestion} type="button"><Check size={14} /> Use this answer</button>
                  <button className="review-skip-button" onClick={onSkipQuestion} type="button"><FastForward size={13} /> Skip this question</button>
                </div>
              </div>
            ) : <div className="review-empty"><Check size={15} /> Your current evidence already answers the priority questions.</div>}
          </section>

          {error ? <div className="notice error">{error}</div> : null}
          <footer className="onboarding-review-finish">
            <div>
              <strong>{reviewReady ? "Your choices are ready to save." : "Review or skip both sections to continue."}</strong>
              <span>CareerFit will not finish onboarding without both decisions.</span>
            </div>
            <button className="button primary" disabled={!reviewReady || saving} onClick={onFinish} type="button">
              {saving ? "Saving your decisions…" : "Enter CareerFit"} <ArrowRight size={16} />
            </button>
          </footer>
        </div>
      </div>
    </main>
  );
}
