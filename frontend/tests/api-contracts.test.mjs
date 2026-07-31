import assert from "node:assert/strict";
import test from "node:test";

import {
  CONTRACT_VALIDATION_MESSAGE,
  ContractValidationError,
  decodeJobScan,
  decodeJobSummaryPage,
  decodeNullableJobScan,
  decodeWorkspaceBootstrap
} from "../lib/api-contracts.mjs";

function validProfile() {
  return {
    id: 1,
    summary: "Backend engineer",
    status: "ready",
    github_url: "",
    linkedin_text: "",
    manual_info: "",
    years_experience: 4,
    onboarding_completed: true,
    recommendations_enabled: false,
    career_interests: ["Backend"],
    last_analyzed_at: "2026-07-30T10:00:00Z",
    updated_at: "2026-07-30T10:00:00Z",
    sources: [{
      id: 2,
      source_type: "cv",
      title: "CV",
      has_text: true,
      read_method: "text",
      scanned_pdf_detected: false,
      ocr_attempted: false,
      ocr_confidence: null,
      ocr_recommended: false,
      updated_at: "2026-07-30T10:00:00Z"
    }],
    facts: [{
      id: 3,
      fact_type: "skill",
      value: "TypeScript",
      evidence: "Built production services",
      confidence: 0.9,
      user_approved: true,
      review_status: "approved",
      support_count: 1,
      source_ids: [2],
      source_id: 2
    }],
    questions: [{
      id: 4,
      field_key: "availability",
      question: "When can you start?",
      answer: "",
      status: "open"
    }]
  };
}

function validJobSummary() {
  return {
    id: 10,
    source_url: "https://jobs.example/10",
    company: "Example",
    role: "Backend Engineer",
    location: "Remote",
    source_confidence: 0.95,
    application_link: "https://jobs.example/10/apply",
    status: "completed",
    error: "",
    created_at: "2026-07-30T09:00:00Z",
    updated_at: "2026-07-30T10:00:00Z",
    requirement_summary: "Build APIs",
    top_skills: ["TypeScript"],
    min_years_experience: 3,
    extraction_completeness: 0.9,
    primary_signal: "Strong evidence",
    match: {
      id: 11,
      score: 84,
      fit_level: "Strong",
      confidence: 0.82,
      status: "Lead",
      analyzed_at: "2026-07-30T10:00:00Z"
    }
  };
}

function validTrackedJob() {
  return {
    id: 10,
    source_url: "https://jobs.example/10",
    company: "Example",
    role: "Backend Engineer",
    location: "Remote",
    description_text: "Build APIs with TypeScript.",
    source_title: "Backend Engineer",
    source_confidence: 0.95,
    application_link: "https://jobs.example/10/apply",
    status: "completed",
    error: "",
    created_at: "2026-07-30T09:00:00Z",
    updated_at: "2026-07-30T10:00:00Z",
    requirements: {
      must_have_skills: ["TypeScript"],
      preferred_skills: ["PostgreSQL"],
      nice_to_have_skills: [],
      all_skills: ["TypeScript", "PostgreSQL"],
      min_years_experience: 3,
      seniority: "Mid",
      education: "",
      work_mode: "Remote",
      domain: "SaaS",
      summary: "Build APIs",
      languages: ["English"],
      location_requirement: "",
      work_authorization: "",
      availability: "",
      responsibilities: ["Build services"],
      evidence_by_requirement: { TypeScript: "Required" },
      ontology_version: "v1",
      skill_groups: [{
        priority: "must_have",
        mode: "all",
        skills: ["TypeScript"],
        evidence: "Required"
      }],
      experience_requirement_known: true,
      reader_version: "v2",
      extraction_completeness: 0.9
    },
    match: {
      id: 11,
      score: 84,
      fit_level: "Strong",
      confidence: 0.82,
      status: "Lead",
      matched_evidence: ["TypeScript"],
      missing_blockers: [],
      gaps: ["PostgreSQL depth"],
      model_version: "v1",
      ontology_version: "v1",
      component_scores: { skills: 90 },
      applied_caps: [],
      status_history: [{
        previous_status: null,
        status: "Lead",
        occurred_at: "2026-07-30T10:00:00Z",
        source: "system",
        note: "",
        created_at: "2026-07-30T10:00:00Z"
      }],
      resume_advice: {
        projects: ["API project"],
        skill_order: ["TypeScript"],
        about_text: "Backend engineer",
        template_id: "default",
        evidence: ["TypeScript"],
        template_version: "about-v1.1.0",
        quality_policy_version: "resume-output-v1.0.0",
        quality_checked: true,
        quality_repaired: false,
        quality_findings: []
      },
      analyzed_at: "2026-07-30T10:00:00Z"
    },
    agent_run: {
      id: 12,
      workflow_type: "job_analysis",
      subject_type: "job",
      subject_id: 10,
      status: "succeeded",
      version: "v1",
      summary: "Completed",
      error: "",
      created_at: "2026-07-30T09:00:00Z",
      completed_at: "2026-07-30T10:00:00Z",
      steps: [{
        id: 13,
        step_key: "read",
        title: "Read",
        status: "succeeded",
        attempt: 1,
        progress: "done",
        output: { requirements: 2 },
        error: "",
        started_at: "2026-07-30T09:00:00Z",
        completed_at: "2026-07-30T10:00:00Z"
      }]
    }
  };
}

function validJobScan(resultJob = null) {
  return {
    id: 20,
    status: resultJob ? "succeeded" : "running",
    current_step: resultJob ? "completed" : "reading",
    progress: resultJob ? 100 : 35,
    result_job_id: resultJob?.id ?? null,
    trace_id: "trace-20",
    error_code: "",
    error_message: "",
    created_at: "2026-07-30T09:00:00Z",
    updated_at: "2026-07-30T10:00:00Z",
    completed_at: resultJob ? "2026-07-30T10:00:00Z" : null,
    result_job: resultJob
  };
}

function assertContractFailure(operation) {
  assert.throws(operation, (error) => (
    error instanceof ContractValidationError
    && error.message === CONTRACT_VALIDATION_MESSAGE
    && !error.message.includes("PRIVATE-CV-CONTENT")
  ));
}

test("durable-state decoders reject null and primitive response bodies", () => {
  for (const decoder of [decodeWorkspaceBootstrap, decodeJobSummaryPage, decodeJobScan]) {
    assertContractFailure(() => decoder(null));
    assertContractFailure(() => decoder("PRIVATE-CV-CONTENT"));
    assertContractFailure(() => decoder(42));
  }
});

test("workspace bootstrap validates profile and job-summary state", () => {
  const payload = {
    user_id: "user-1",
    profile: validProfile(),
    jobs: [validJobSummary()],
    jobs_next_cursor: "cursor-1",
    jobs_watermark: "2026-07-30T10:00:00Z"
  };

  assert.equal(decodeWorkspaceBootstrap(payload), payload);
  assertContractFailure(() => decodeWorkspaceBootstrap({ ...payload, profile: null }));
  assertContractFailure(() => decodeWorkspaceBootstrap({
    ...payload,
    profile: { ...payload.profile, facts: [null] }
  }));
});

test("job summary page rejects malformed nested matches", () => {
  const payload = {
    items: [validJobSummary()],
    next_cursor: null,
    watermark: "2026-07-30T10:00:00Z"
  };

  assert.equal(decodeJobSummaryPage(payload), payload);
  assertContractFailure(() => decodeJobSummaryPage({
    ...payload,
    items: [{ ...validJobSummary(), match: 42 }]
  }));
});

test("job scan accepts queued null results and validates a complete result job", () => {
  const running = validJobScan();
  const succeeded = validJobScan(validTrackedJob());

  assert.equal(decodeJobScan(running), running);
  assert.equal(decodeJobScan(succeeded), succeeded);
  assert.equal(decodeNullableJobScan(null), null);
});

test("job scan rejects invalid states and malformed nested result jobs", () => {
  assertContractFailure(() => decodeJobScan({
    ...validJobScan(),
    status: "PRIVATE-CV-CONTENT"
  }));
  assertContractFailure(() => decodeJobScan({
    ...validJobScan(validTrackedJob()),
    result_job: { ...validTrackedJob(), requirements: null }
  }));
  assertContractFailure(() => decodeJobScan({
    PRIVATE_CV_TEXT: "PRIVATE-CV-CONTENT"
  }));
});
