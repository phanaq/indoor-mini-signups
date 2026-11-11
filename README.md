# Indoor Mini Signups

A Streamlit app backed by its own Supabase project for Wednesday mini at ComEd (9:30–10:30pm). The dates are Nov 18 and 25 and Dec 2, 9 and 16. Players pay at each session (pay what you can), not ahead of time.

## Setup (about 10 minutes)

1. **Supabase:** create a new project. In the SQL Editor, paste and run [`supabase/schema.sql`](supabase/schema.sql). This creates `mini_sessions`, `mini_signups` and `mini_feedback`, and adds the 5 dates.
2. **Secrets:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill it in. Use the project URL and the **service_role** key from Project Settings → API. Then pick an admin password.
3. **Run locally:**
   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/streamlit run app.py
   ```
4. **Share it:** push the folder to GitHub, without `secrets.toml`, which is already in `.gitignore`. Deploy it on [share.streamlit.io](https://share.streamlit.io) and paste the secrets into App settings → Secrets.

## What's in it

| Tab | Who | What |
|---|---|---|
| **Sign up** | everyone | Enter your name and matchup, check the dates you can make, and give feedback on mixed vs WMP-only. Entering the same name again loads your earlier answers so you can change them. |
| **Who's going** | everyone | Each date's roster with WMP/MMP/Either counts, plus a per-person cost estimate once you set the court cost. |
| **Admin** | you (password) | A format planner, a check-in sheet (here / paid / amount / Venmo-cash), walk-ins, each session's format, cap and cost, a season grid, a CSV export and a feedback tally. |

- Players can't change a session after it starts (Chicago time).
- MMP players can't sign up for a date marked WMP-only. If you flip a date to WMP-only after MMP players signed up, the admin tab lists them so you can message them.
- On the check-in sheet, typing an amount marks that player as paid automatically.

## Choosing WMP-only dates

### What decides it

Mini is 4v4, so a playable night needs about **8 people, ideally 10–12** so there are subs. One hour is short and people will tire.

- **A date can be WMP-only** if **≥ 8 WMP** signed up for it, counting "Either" players.
- **A date should be mixed** if WMP is short of 8 but each side has at least 4.
- **Below that**, recruit for the date, or move the date's players to the format that does fill.

The admin **Format planner** applies these rules to each date. You can change the thresholds in secrets with `WMP_ONLY_MIN` and `MIXED_MIN_EACH`.

The court costs the same however many people come, so a WMP-only night with 8 people costs each player more than a mixed night with 14. Keep that in mind with PWYC. Mixed nights can bring in a bit extra to cover the smaller ones.

### Two rounds: availability first, then format

Ask about availability before you announce formats. If formats are set first, people sign up based on the format, and you can no longer tell what the real demand is.

| When | Step |
|---|---|
| **Wed Nov 11 (today)** | Post the app link in the Slack thread. Ask everyone, including people who already reacted, to fill it out by **Sun Nov 15, 8pm**. All dates show "Format TBD". |
| **Fri Nov 13** | Send one reminder. Tag people who reacted 👍/➗ but haven't filled it out yet. |
| **Sun Nov 15, evening** | Open the Format planner and look at each date's WMP count and the feedback tally. **Set the format for all 5 dates.** |
| **Mon Nov 16** | Announce the schedule, for example "Nov 18 mixed, Dec 2 + Dec 16 WMP-only…". Tell MMP players to check their dates; anyone signed up for a date that's now WMP-only shows up on the admin warning. Optionally set a cap. |
| **Mon before each date** | Check that date's numbers. If it's under 8, post a "need N more for Wednesday" call. You can still change the format, but only on Monday so people get 2 days' notice. Avoid changes after that. |
| **Each Wednesday** | Use the check-in sheet as people arrive and record payments. Afterwards, compare the money collected with the court cost. |

### What I'd expect, before seeing any data

- **Nov 18 → mixed.** Use the first night to draw the biggest group and get people in the habit.
- **Nov 25 → mixed, or keep it flexible.** It's the night before Thanksgiving, so plenty of people will be traveling. Expect low numbers and use the larger pool.
- **2 of the remaining 3 as WMP-only** (for example Dec 2 and Dec 16), with Dec 9 mixed, if the signups have 8+ WMP on those dates. Alternating spreads the WMP nights across the season, and MMP players get 3 of 5 nights.
- If the feedback leans strongly one way, follow it. If WMP numbers are thin (5–7), make **every** date mixed rather than running a WMP-only night that can't fill.

### Message you can post in Slack

> Thanks for the reacts! Please fill this out by **Sun 11/15 8pm** so I can plan: <link>
> Check every date you think you'll make it to (you can edit it later) and tell me what you think about mixed vs WMP-only nights. I'll announce which dates are which on Mon 11/16. No payment now, it's pay-what-you-can at each session 💜
