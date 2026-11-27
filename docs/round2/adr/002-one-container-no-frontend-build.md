# ADR-002: One Python FastAPI container with a plain HTML and JS front end

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** the judges start the app with one command; "if it does not start, your build cannot move ahead". We
  have 3.5 days and a small team.
- **Options:** (1) FastAPI serving static HTML, CSS and JS; (2) FastAPI + a React/Vite front end in a second container;
  (3) Next.js full stack.
- **Decision:** option 1. One `Dockerfile`, one service in `docker-compose.yml`, no Node build step.
- **Consequences:** fewer ways for the judges' start to fail and faster builds. The UI code is simpler and less fancy;
  acceptable for "a working prototype, not a full product". Python also matches the AI and eval code.
