"use client";

import { useState } from "react";
import type { ClarificationQuestion } from "@/lib/api";

export function ClarificationPanel({ questions, onAnswer }: { questions: ClarificationQuestion[]; onAnswer: (id: number, answer: string) => Promise<void> }) {
  return (
    <div className="panel questions-panel">
      <span className="section-kicker">Complete the signal</span><h2>A few things need your input</h2>
      <p className="panel-intro">Each answer disappears once saved and may reveal the next useful question.</p>
      <div className="question-list">{questions.map((question) => <QuestionRow key={question.id} question={question} onAnswer={onAnswer} />)}</div>
    </div>
  );
}

function QuestionRow({ question, onAnswer }: { question: ClarificationQuestion; onAnswer: (id: number, answer: string) => Promise<void> }) {
  const [answer, setAnswer] = useState(question.answer);
  const [saving, setSaving] = useState(false);
  async function submit() { setSaving(true); try { await onAnswer(question.id, answer); } finally { setSaving(false); } }
  return <div className="question-row"><span className={`chip ${question.status === "answered" ? "ready-chip" : ""}`}>{question.status}</span><strong>{question.question}</strong><textarea onChange={(event) => setAnswer(event.target.value)} value={answer} /><button className="button compact" disabled={saving || !answer.trim()} onClick={() => void submit()} type="button">Save answer</button></div>;
}
