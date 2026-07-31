"use client";

import { Route, Sparkles } from "lucide-react";
import type { ProfileFact } from "@/lib/api";

const DIRECTION_SKILLS: Record<string, string[]> = {
  "Software Engineering": ["javascript", "typescript", "python", "java", "c#", "c++", "go", "rust", "node", "api", "sql"],
  "AI, Data Science, ML & Algorithms": ["python", "machine learning", "deep learning", "pytorch", "tensorflow", "pandas", "numpy", "nlp", "computer vision"],
  "Data Analytics": ["sql", "python", "excel", "tableau", "power bi", "pandas", "analytics"],
  "Frontend Development": ["javascript", "typescript", "react", "next.js", "vue", "angular", "html", "css", "tailwind"],
  "Mobile Development": ["react native", "flutter", "swift", "kotlin", "ios", "android", "dart"],
  DevOps: ["docker", "kubernetes", "terraform", "aws", "azure", "gcp", "ci/cd", "linux"],
  QA: ["testing", "playwright", "selenium", "cypress", "pytest", "automation", "quality assurance"],
  "Embedded, Low-Level & Firmware": ["c", "c++", "rust", "embedded", "firmware", "rtos", "microcontroller"],
  "Hardware Engineering": ["verilog", "vhdl", "fpga", "pcb", "electronics", "hardware"],
  "Mechanical Engineering": ["solidworks", "cad", "mechanical", "manufacturing", "simulation"],
  "Systems Engineering": ["systems", "architecture", "linux", "networking", "integration"],
  Sales: ["sales", "crm", "negotiation", "account management", "pipeline"],
  "Customer Success": ["customer success", "support", "onboarding", "account management", "crm"],
  Cybersecurity: ["security", "cybersecurity", "penetration testing", "siem", "networking", "linux"],
  "IT & System Administration": ["linux", "windows", "networking", "active directory", "support", "cloud"],
  "UI/UX & Content Design": ["figma", "user research", "ux", "ui", "prototyping", "design systems"],
  "Product Management": ["product", "roadmap", "analytics", "user research", "agile", "stakeholder"],
  Operations: ["operations", "process", "logistics", "excel", "analytics"],
  Marketing: ["marketing", "seo", "content", "analytics", "campaign", "social media"],
  "HR & Recruitment": ["recruitment", "human resources", "talent", "interviewing", "people operations"],
  "Project Management": ["project management", "agile", "scrum", "jira", "stakeholder", "planning"],
  "Finance & Accounting": ["finance", "accounting", "excel", "financial analysis", "budgeting"],
  "Executive / C-Level": ["strategy", "leadership", "operations", "business development", "management"],
  "Business Development": ["business development", "partnerships", "sales", "strategy", "market research"],
  "Legal, Compliance & Policy": ["legal", "compliance", "policy", "risk", "privacy"]
};

export function CareerDirectionPreview({ interests, facts }: { interests: string[]; facts: ProfileFact[] }) {
  const skillFacts = facts.filter((fact) => fact.fact_type === "skill" && fact.review_status !== "rejected");
  const directions = interests
    .map((interest, index) => {
      const keywords = DIRECTION_SKILLS[interest] ?? [];
      const evidence = skillFacts.filter((fact) => keywords.some((keyword) => skillMatches(fact.value, keyword)));
      const score = evidence.reduce((total, fact) => total + fact.confidence, 0);
      return { interest, evidence, score, index };
    })
    .toSorted((left, right) => right.score - left.score || right.evidence.length - left.evidence.length || left.index - right.index)
    .slice(0, 3);

  return (
    <section className="direction-preview" aria-labelledby="direction-preview-title">
      <div className="review-section-heading">
        <span aria-hidden><Route size={17} /></span>
        <div>
          <small>Direction preview</small>
          <h2 id="direction-preview-title">Where your evidence points</h2>
          <p>These are starting directions, not predictions. Job matches will sharpen them.</p>
        </div>
      </div>
      <div className="direction-grid">
        {directions.map(({ interest, evidence }, index) => {
          const label = evidence.length >= 3 ? "Strong evidence" : evidence.length ? "Promising signal" : "Chosen direction";
          return (
            <article className="direction-card" key={interest}>
              <div><span>0{index + 1}</span><small>{label}</small></div>
              <h3>{interest}</h3>
              {evidence.length ? (
                <p dir="auto"><Sparkles size={12} /> Supported by {evidence.slice(0, 3).map((fact) => fact.value).join(", ")}</p>
              ) : (
                <p>Add role-specific evidence later to make this direction more precise.</p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function skillMatches(value: string, keyword: string) {
  const normalized = value.toLowerCase().trim();
  if (keyword.length <= 2) return normalized === keyword || normalized.startsWith(`${keyword} `);
  return normalized === keyword || normalized.includes(keyword) || keyword.includes(normalized);
}
