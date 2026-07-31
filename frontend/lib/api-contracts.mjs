export const CONTRACT_VALIDATION_MESSAGE = "Invalid API response contract.";

export class ContractValidationError extends Error {
  constructor() {
    super(CONTRACT_VALIDATION_MESSAGE);
    this.name = "ContractValidationError";
  }
}

const JOB_STATUSES = new Set(["Lead", "Applied", "Interview", "Rejected", "Withdrawn", "Offer"]);
const FIT_LEVELS = new Set(["Strong", "Medium", "Weak"]);
const SCAN_STATUSES = new Set(["queued", "running", "succeeded", "failed", "cancel_requested", "cancelled"]);
const FACT_REVIEW_STATUSES = new Set(["pending", "approved", "rejected"]);
const OUTPUT_QUALITY_SEVERITIES = new Set(["error", "warning"]);
const STATUS_EVENT_SOURCES = new Set(["system", "user", "correction", "backfill", "legacy"]);

function fail() {
  throw new ContractValidationError();
}

function record(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail();
  return value;
}

function string(value) {
  if (typeof value !== "string") fail();
}

function nullableString(value) {
  if (value !== null) string(value);
}

function boolean(value) {
  if (typeof value !== "boolean") fail();
}

function finiteNumber(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) fail();
}

function integer(value) {
  finiteNumber(value);
  if (!Number.isInteger(value)) fail();
}

function nullableInteger(value) {
  if (value !== null) integer(value);
}

function array(value, validator) {
  if (!Array.isArray(value)) fail();
  for (const item of value) validator(item);
}

function stringArray(value) {
  array(value, string);
}

function integerArray(value) {
  array(value, integer);
}

function enumValue(value, allowed) {
  string(value);
  if (!allowed.has(value)) fail();
}

function stringRecord(value) {
  const data = record(value);
  for (const item of Object.values(data)) string(item);
}

function numberRecord(value) {
  const data = record(value);
  for (const item of Object.values(data)) finiteNumber(item);
}

function profileSource(value) {
  const data = record(value);
  integer(data.id);
  string(data.source_type);
  string(data.title);
  boolean(data.has_text);
  string(data.read_method);
  boolean(data.scanned_pdf_detected);
  boolean(data.ocr_attempted);
  if (data.ocr_confidence !== null) finiteNumber(data.ocr_confidence);
  boolean(data.ocr_recommended);
  string(data.updated_at);
}

function profileFact(value) {
  const data = record(value);
  integer(data.id);
  string(data.fact_type);
  string(data.value);
  string(data.evidence);
  finiteNumber(data.confidence);
  boolean(data.user_approved);
  enumValue(data.review_status, FACT_REVIEW_STATUSES);
  integer(data.support_count);
  integerArray(data.source_ids);
  nullableInteger(data.source_id);
}

function clarificationQuestion(value) {
  const data = record(value);
  integer(data.id);
  string(data.field_key);
  string(data.question);
  string(data.answer);
  string(data.status);
}

function profile(value) {
  const data = record(value);
  nullableInteger(data.id);
  string(data.summary);
  string(data.status);
  string(data.github_url);
  string(data.linkedin_text);
  string(data.manual_info);
  finiteNumber(data.years_experience);
  boolean(data.onboarding_completed);
  boolean(data.recommendations_enabled);
  stringArray(data.career_interests);
  nullableString(data.last_analyzed_at);
  nullableString(data.updated_at);
  array(data.sources, profileSource);
  array(data.facts, profileFact);
  array(data.questions, clarificationQuestion);
}

function jobMatchSummary(value) {
  const data = record(value);
  integer(data.id);
  finiteNumber(data.score);
  enumValue(data.fit_level, FIT_LEVELS);
  finiteNumber(data.confidence);
  enumValue(data.status, JOB_STATUSES);
  string(data.analyzed_at);
}

function jobSummary(value) {
  const data = record(value);
  integer(data.id);
  string(data.source_url);
  string(data.company);
  string(data.role);
  string(data.location);
  finiteNumber(data.source_confidence);
  string(data.application_link);
  string(data.status);
  string(data.error);
  string(data.created_at);
  string(data.updated_at);
  string(data.requirement_summary);
  stringArray(data.top_skills);
  finiteNumber(data.min_years_experience);
  finiteNumber(data.extraction_completeness);
  string(data.primary_signal);
  if (data.match !== null) jobMatchSummary(data.match);
}

function skillGroup(value) {
  const data = record(value);
  string(data.priority);
  string(data.mode);
  stringArray(data.skills);
  string(data.evidence);
}

function jobRequirements(value) {
  const data = record(value);
  stringArray(data.must_have_skills);
  stringArray(data.preferred_skills);
  stringArray(data.nice_to_have_skills);
  stringArray(data.all_skills);
  finiteNumber(data.min_years_experience);
  string(data.seniority);
  string(data.education);
  string(data.work_mode);
  string(data.domain);
  string(data.summary);
  stringArray(data.languages);
  string(data.location_requirement);
  string(data.work_authorization);
  string(data.availability);
  stringArray(data.responsibilities);
  stringRecord(data.evidence_by_requirement);
  string(data.ontology_version);
  array(data.skill_groups, skillGroup);
  boolean(data.experience_requirement_known);
  string(data.reader_version);
  finiteNumber(data.extraction_completeness);
}

function resumeAdvice(value) {
  const data = record(value);
  stringArray(data.projects);
  stringArray(data.skill_order);
  string(data.about_text);
  string(data.template_id);
  stringArray(data.evidence);
  string(data.template_version);
  string(data.quality_policy_version);
  boolean(data.quality_checked);
  boolean(data.quality_repaired);
  array(data.quality_findings, outputQualityFinding);
}

function outputQualityFinding(value) {
  const data = record(value);
  string(data.code);
  enumValue(data.severity, OUTPUT_QUALITY_SEVERITIES);
  string(data.message);
}

function statusHistoryItem(value) {
  const data = record(value);
  if (data.previous_status !== null) enumValue(data.previous_status, JOB_STATUSES);
  enumValue(data.status, JOB_STATUSES);
  string(data.occurred_at);
  enumValue(data.source, STATUS_EVENT_SOURCES);
  string(data.note);
  string(data.created_at);
}

function jobMatch(value) {
  const data = record(value);
  integer(data.id);
  finiteNumber(data.score);
  enumValue(data.fit_level, FIT_LEVELS);
  finiteNumber(data.confidence);
  enumValue(data.status, JOB_STATUSES);
  stringArray(data.matched_evidence);
  stringArray(data.missing_blockers);
  stringArray(data.gaps);
  string(data.model_version);
  string(data.ontology_version);
  numberRecord(data.component_scores);
  stringArray(data.applied_caps);
  array(data.status_history, statusHistoryItem);
  resumeAdvice(data.resume_advice);
  string(data.analyzed_at);
}

function agentStep(value) {
  const data = record(value);
  integer(data.id);
  string(data.step_key);
  string(data.title);
  string(data.status);
  integer(data.attempt);
  string(data.progress);
  record(data.output);
  string(data.error);
  string(data.started_at);
  nullableString(data.completed_at);
}

function agentRun(value) {
  const data = record(value);
  integer(data.id);
  string(data.workflow_type);
  string(data.subject_type);
  nullableInteger(data.subject_id);
  string(data.status);
  string(data.version);
  string(data.summary);
  string(data.error);
  string(data.created_at);
  nullableString(data.completed_at);
  array(data.steps, agentStep);
}

function trackedJob(value) {
  const data = record(value);
  integer(data.id);
  string(data.source_url);
  string(data.company);
  string(data.role);
  string(data.location);
  string(data.description_text);
  string(data.source_title);
  finiteNumber(data.source_confidence);
  string(data.application_link);
  string(data.status);
  string(data.error);
  string(data.created_at);
  string(data.updated_at);
  jobRequirements(data.requirements);
  if (data.match !== null) jobMatch(data.match);
  if (data.agent_run !== null) agentRun(data.agent_run);
}

export function decodeWorkspaceBootstrap(value) {
  const data = record(value);
  string(data.user_id);
  profile(data.profile);
  array(data.jobs, jobSummary);
  nullableString(data.jobs_next_cursor);
  nullableString(data.jobs_watermark);
  return data;
}

export function decodeJobSummaryPage(value) {
  const data = record(value);
  array(data.items, jobSummary);
  nullableString(data.next_cursor);
  nullableString(data.watermark);
  return data;
}

export function decodeJobScan(value) {
  const data = record(value);
  integer(data.id);
  enumValue(data.status, SCAN_STATUSES);
  string(data.current_step);
  finiteNumber(data.progress);
  nullableInteger(data.result_job_id);
  string(data.trace_id);
  string(data.error_code);
  string(data.error_message);
  string(data.created_at);
  string(data.updated_at);
  nullableString(data.completed_at);
  if (data.result_job !== null) trackedJob(data.result_job);
  return data;
}

export function decodeNullableJobScan(value) {
  return value === null ? null : decodeJobScan(value);
}
