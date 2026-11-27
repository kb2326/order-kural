# Discord: how to follow the hackathon server (decided 2026-11-17)

- **Not allowed:**
  - adding a bot to the hackathon's server (only its admins can do that);
  - automating the owner's personal account ("self-bot": against Discord's Terms; the account can be banned).
- **Allowed and useful:**
  1. Create a small private Discord server.
  2. On the hackathon's announcement channel (megaphone icon), click **Follow** and choose that server. New
     announcements are then copied there automatically.
  3. Create a bot in the Discord Developer Portal (https://discord.com/developers), add it to the private server, and
     put its token in `.env` as `DISCORD_BOT_TOKEN`.
  4. Connect a Discord MCP server (community-built) or a small script with that bot token, so the agent can read and
     summarise the copied announcements (problem statement, rules, deadlines).
- **What this does not cover:** general chat channels cannot be followed. Copy anything important from them by hand.
- **Status:** not set up yet. The owner said yes to the idea in principle; nothing is built.
