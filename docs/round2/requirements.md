# Round 2 requirements (collected 2026-11-27)

**Sources, in order of trust:**
1. The signed-in dashboard, the "Build requirements" page and the "Submit your build" form, all pasted by the owner on
   27 Nov. Where sources disagree, these win.
2. The public pages https://hackos.scaler.com/wispr/ and `/dashboard.html`, fetched 27 Nov. They are partly prototype
   ("Quality results and scores are simulated") and give older dates.

## Deadline

- **Submit by 30 Nov, 11:59 pm** (dashboard countdown and form). The public landing page still says 29 Nov; ignore it.
- **One submission per team, and only once.** It cannot be edited after submitting.
- **Keep everything public and working until 2 Dec.** The organisers test every link to decide results.
- Shortlist: 2 Dec. Finale: 13 Dec, on campus (city not stated). At the finale we "build the full version".

## The brief

> The main task in your product is done by speaking. Think of something people in India do today by typing, tapping
> or filling forms, and make it work by voice.

- **Pick one theme:**
  - Public infrastructure and civic services
  - Healthcare access
  - Inclusive education
  - **Livelihoods and small business** (ours)
  - Everyday access for all
- **Extend the Round 1 idea, or start a new one.** We extend Order Kural.
- **Scope:** "A working prototype, not a full product." "One core flow that works end to end."

## What to submit

| # | Item | Hard rules | Our check |
|---|---|---|---|
| 1 | **Code on GitHub** | **Public** repo. **`docker-compose.yml`**: the app starts with one command. **Starts and shows its main screen with no secret keys**; a feature that needs a key shows "key not set". **About 300+ lines of our own code, written during the hackathon**; a starter template with small changes fails. "If it does not start, your build cannot move ahead." | Fresh-clone test on a second machine (the friend's) |
| 2 | **Demo video on YouTube** | Public or unlisted, **3 minutes or less**, showing the product working | |
| 3 | **Pitch deck (PDF)** | Up to 10 MB. **They read the words, not the pictures**, so the key points must be text. Must cover: **problem and solution**; **who it is for and how many users there could be**; **what it depends on** (voice tools, AI models, services) **and what happens if they get costly or stop working**; **launch plan** (first users, growth) | |
| 4 | **Live link** (optional) | Anyone can try it; small bonus if it works; never counts against us. We host it ourselves | |

**Form fields:** build type (extension of Round 1), project name, theme, state (Tamil Nadu), the four links or files,
and four tick boxes: repo public and starts without keys; video public or unlisted; deck is a PDF; build instructions
read and followed.

## Scoring

- **Round 2 judging criteria and weights are not published.** FAQ 07 says criteria are "shared in that round's
  details", but the owner confirmed on 27 Nov that the dashboard has no evaluation details. So we build to our own
  proxy rubric (below) and can ask on Discord / wispr.support@scaler.com.
- Known: Round 1 (Activities 2 + 3) counts for 10% of the final score (FAQ, 20 Nov). Prizes rank by "highest total
  score".
- **What we infer from the rules** (guesses, to confirm): it must start (pass/fail gate); voice must be the main way in;
  one flow working end to end; the deck is judged on its text.

### Our proxy rubric (our guess at what judges check, built from the stated rules)

1. **Gate (pass/fail):** public repo; `docker compose up` works; main screen shows with no keys; 300+ own lines.
2. **Voice is the main way in:** the core task is done by speaking, not tapping.
3. **One flow works end to end:** shown in the video, ideally on a live link.
4. **Real Indian need:** a real user, real language mix, a realistic number of users (deck).
5. **Honest dependencies:** what we rely on and the fallback if it fails or gets costly (deck).
6. **Launch plan:** how the first users are reached (deck).

## Other rules that apply

- **AI tools allowed** (FAQ 09: ChatGPT, Claude, Cursor).
- **"Build your answer by voice"** with Wispr Flow is the theme. No proof is required, but showing it briefly in the
  video fits the theme.
- **Team:** locked (the owner and one friend).
- **Masterclass** (25 Nov, "From idea to prototype") was missed; the recording is on the dashboard. Worth 30 minutes:
  the organisers may hint at what they judge.

## Open questions

1. ~~What does "How builds are evaluated" say?~~ Not available (owner, 27 Nov). Ask the organisers if time allows.
2. The public dashboard mentions a "Docker template". Is there an official template we should start from, or is any
   `docker-compose.yml` fine? The build page says only "Add a Docker setup file (docker-compose.yml)".
3. Does "about 300 lines of our own code" count frontend code? Assume yes, but write well over 300 lines of real logic.
