# AutoJobHunt — Fedora Handover

> **For the AI agent reading this after Rishi reinstalls on Fedora:**  
> Read `FEDORA_HANDOVER.md` in this project's artifact directory first.  
> The full handover with setup steps, next features, and git state is there.  
> Short summary is below.

## Who / What / Where

- **Owner:** Rishi Thakur (`rishi_th219@proton.me`)
- **Repo:** https://github.com/rishi-th219/autojobhunt.git
- **Clone to:** `~/Jobhunt/Bot/`
- **Python:** Use venv — `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`

## The One Big Thing Left To Do

Build a **free hosted multi-user personalized job alert platform**:
- GitHub Actions runs the scraper hourly (free)
- Supabase stores user profiles + matched jobs (free)
- Vercel/GitHub Pages hosts the web signup/dashboard (free)
- Each user gets tailored email alerts + downloadable opportunities.xlsx

Full spec and prerequisites are in `FEDORA_HANDOVER.md`.

## 3 Commits Pending Push

Run `git push origin main` after cloning. 3 local commits haven't been pushed yet.

## Files NOT in Git (Must Recreate)

- `.env` — copy from `.env.example`, add SMTP credentials
- `config/profile.yml` — Rishi's canonical profile (see FEDORA_HANDOVER.md §1 for key facts)
- `opportunities.xlsx` — auto-regenerates on first scan run
