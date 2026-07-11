# Career Fit AI

Fresh MVP for profile-aware job matching.

Beta: https://career-fit-ai-sigma.vercel.app
API health: https://career-fit-ai-api.vercel.app/api/health

The beta does not use OpenAI, ChatGPT, or another hosted generative model. Profile extraction, job requirement classification, fit scoring, and resume About text run through versioned application-owned rules and templates in the FastAPI backend.

## Scope

- Public beta accounts through Supabase Auth, protected by atomic Postgres-backed signup/API rate limits.
- First-use onboarding plus authenticated Home and Profile pages.
- One required CV PDF.
- Optional GitHub, LinkedIn PDF/text, and manual notes.
- Editable career interests based on Goozali's public role taxonomy.
- Saved job scans with dedupe.
- Weighted fit model with hard penalties for must-have and experience mismatches.
- Versioned skill ontology, evidence strength, eligibility caps, and auditable score components.
- Twenty-four evidence-backed About templates selected by career stage and role family.
- Lead, Applied, Interview, Rejected, Withdrawn, and Offer outcome history.
- Resume advice for each job: projects, skill order, and a fitting About section.
- Cached JWKS token verification and a one-call workspace bootstrap for faster authenticated loading.
- Scanned-PDF detection with an optional private OCR fallback configured through `OCR_SERVICE_URL`.

Out of scope for v1: Goozali scanning, Gmail, WhatsApp, automatic applications, multiple CVs, and LinkedIn scraping.

## Local development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Supabase setup

1. Create a Supabase project.
2. Run `supabase/schema.sql` in the Supabase SQL editor.
3. Create a private Storage bucket named `profile-documents`.
4. Keep email/password Auth enabled. The app signup route creates confirmed beta users and applies signup rate limits.
5. Put the project URL, anon key, service role key, backend API key, and allowed origins in Vercel/local env.

For an existing database, apply the SQL files in `supabase/migrations/` in filename order instead of rerunning the base schema.

Use the API project URL in the form `https://<project-ref>.supabase.co`, not the Supabase dashboard URL. Use a publishable key for browser/auth requests and a secret key only in backend/Vercel environment variables.

## Fit score meaning

The match percentage measures evidence alignment with a saved job posting. It is not a prediction that the user will receive an interview or offer. Confidence is reported separately and missing information creates clarification questions.

For local development without Supabase configured, the backend accepts a development fallback user, but the frontend auth screens need Supabase env values.

## Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest

cd ..\frontend
npm run typecheck
npm run build
```
