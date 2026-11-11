"""Indoor Mini signups — Streamlit + Supabase.

Players sign up for the Wednesday mini dates they plan to attend.
Payment is collected at each session (PWYC), and the admin tab is used
as a check-in sheet to record attendance and who paid what.
"""
from __future__ import annotations

import hmac
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import Client, create_client

TZ = ZoneInfo("America/Chicago")
FORMAT_LABELS = {"tbd": "Format TBD", "mixed": "Mixed", "wmp": "WMP only"}
FORMAT_EMOJI = {"tbd": "❔", "mixed": "🔀", "wmp": "💜"}
MATCHUPS = ["WMP", "MMP", "Either"]
PREFERENCES = {
    "some_of_each": "Some mixed, some WMP-only",
    "mixed": "All mixed",
    "wmp": "All WMP-only",
    "no_preference": "No preference",
}
PAYMENT_METHODS = ["", "Venmo", "Zelle", "Cash", "PayPal", "Other"]

st.set_page_config(page_title="Indoor Mini Signups", page_icon="🥏", layout="centered")


# ── Supabase ────────────────────────────────────────────────────────────────
@st.cache_resource
def db() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_data(ttl=30)
def load_sessions() -> list[dict]:
    return db().table("mini_sessions").select("*").order("session_date").execute().data


@st.cache_data(ttl=30)
def load_signups() -> list[dict]:
    return db().table("mini_signups").select("*").order("created_at").execute().data


@st.cache_data(ttl=30)
def load_feedback() -> list[dict]:
    return db().table("mini_feedback").select("*").order("updated_at").execute().data


def refresh() -> None:
    load_sessions.clear()
    load_signups.clear()
    load_feedback.clear()


# ── Helpers ─────────────────────────────────────────────────────────────────
def player_key(name: str) -> str:
    return " ".join(name.lower().split())


def session_start(s: dict) -> datetime:
    d = date.fromisoformat(s["session_date"])
    t = time.fromisoformat(s["start_time"])
    return datetime.combine(d, t, tzinfo=TZ)


def is_locked(s: dict) -> bool:
    """Players can't change a session once it has started."""
    return datetime.now(TZ) >= session_start(s)


def fmt_time(t: str) -> str:
    return time.fromisoformat(t).strftime("%-I:%M%p").lower()


def session_label(s: dict) -> str:
    d = date.fromisoformat(s["session_date"])
    return f"{d.strftime('%a %b %-d')} · {fmt_time(s['start_time'])}–{fmt_time(s['end_time'])}"


def format_badge(s: dict) -> str:
    if s["is_cancelled"]:
        return "🚫 Cancelled"
    return f"{FORMAT_EMOJI[s['format']]} {FORMAT_LABELS[s['format']]}"


def going(signups: list[dict], session_id: int) -> list[dict]:
    return [r for r in signups if r["session_id"] == session_id and r["status"] == "going"]


def money(x) -> str:
    return f"${float(x or 0):,.2f}".replace(".00", "")


# ── Sign up tab ─────────────────────────────────────────────────────────────
def signup_tab(sessions: list[dict], signups: list[dict], feedback: list[dict]) -> None:
    st.markdown(
        "**Wednesdays 9:30–10:30pm at ComEd.** Pick every date you think you'll make it to "
        "and update it here if plans change.\n\n"
        "💵 **Pay at the session — pay what you can.** No need to pay ahead of time."
    )
    pay_note = st.secrets.get("PAYMENT_NOTE")
    if pay_note:
        st.caption(pay_note)

    name = st.text_input("Your name (first + last initial is fine)", max_chars=60).strip()
    if not name:
        st.info("Enter your name to sign up or to edit your existing signups.")
        return
    key = player_key(name)

    mine = {r["session_id"]: r for r in signups if r["player_key"] == key}
    my_fb = next((f for f in feedback if f["player_key"] == key), None)
    any_prev = next(iter(mine.values()), None)
    if any_prev:
        st.success(f"Welcome back — loaded your signups as **{any_prev['player_name']}**.")

    with st.form(f"signup-{key}"):
        contact = st.text_input(
            "Slack handle (optional)", value=(any_prev or {}).get("contact") or ""
        )
        default_matchup = (any_prev or {}).get("matchup", "WMP")
        matchup = st.radio(
            "Matchup", MATCHUPS, index=MATCHUPS.index(default_matchup), horizontal=True
        )

        st.markdown("**Which dates can you make?**")
        picks: dict[int, bool] = {}
        for s in sessions:
            existing = mine.get(s["id"])
            already_going = bool(existing and existing["status"] == "going")
            count = len(going(signups, s["id"]))
            spots = ""
            if s["capacity"]:
                spots = f" · {count}/{s['capacity']} spots"
                full = count >= s["capacity"] and not already_going
            else:
                spots = f" · {count} going"
                full = False
            locked = is_locked(s) or s["is_cancelled"]
            suffix = " (full)" if full else " (closed)" if is_locked(s) else ""
            picks[s["id"]] = st.checkbox(
                f"{session_label(s)} — {format_badge(s)}{spots}{suffix}",
                value=already_going,
                disabled=locked or full,
                key=f"pick-{key}-{s['id']}",
            )

        st.markdown("**Feedback:** some dates may be mixed and some WMP-only. What would you like?")
        pref_keys = list(PREFERENCES)
        default_pref = (my_fb or {}).get("preference", "some_of_each")
        preference = st.radio(
            "Format preference",
            pref_keys,
            index=pref_keys.index(default_pref),
            format_func=PREFERENCES.get,
            label_visibility="collapsed",
        )
        comments = st.text_area(
            "Anything else? (optional)", value=(my_fb or {}).get("comments") or "", max_chars=500
        )
        submitted = st.form_submit_button("Save my signups", type="primary")

    if not submitted:
        return

    if matchup == "MMP":
        wmp_picked = [s for s in sessions if s["format"] == "wmp" and picks[s["id"]] and not is_locked(s)]
        if wmp_picked:
            st.error(
                "These dates are WMP-only — please uncheck them: "
                + ", ".join(session_label(s) for s in wmp_picked)
            )
            return

    upserts, cancels = [], []
    for s in sessions:
        if is_locked(s) or s["is_cancelled"]:
            continue  # never touch past/cancelled sessions from the player side
        existing = mine.get(s["id"])
        if picks[s["id"]]:
            upserts.append(
                {
                    "session_id": s["id"],
                    "player_name": name,
                    "player_key": key,
                    "contact": contact.strip() or None,
                    "matchup": matchup,
                    "status": "going",
                }
            )
        elif existing and existing["status"] == "going":
            cancels.append(existing["id"])

    # Re-check capacity against fresh data to avoid oversubscribing.
    load_signups.clear()
    fresh = load_signups()
    for row in upserts:
        s = next(x for x in sessions if x["id"] == row["session_id"])
        others = [r for r in going(fresh, s["id"]) if r["player_key"] != key]
        if s["capacity"] and len(others) >= s["capacity"]:
            st.error(f"Sorry, {session_label(s)} just filled up. Your other dates were not saved yet — uncheck it and try again.")
            return

    client = db()
    if upserts:
        client.table("mini_signups").upsert(upserts, on_conflict="session_id,player_key").execute()
    if cancels:
        client.table("mini_signups").update({"status": "cancelled"}).in_("id", cancels).execute()
    client.table("mini_feedback").upsert(
        {
            "player_name": name,
            "player_key": key,
            "preference": preference,
            "comments": comments.strip() or None,
            "updated_at": datetime.now(TZ).isoformat(),
        },
        on_conflict="player_key",
    ).execute()
    refresh()
    n = len(upserts)
    st.success(f"Saved! You're signed up for {n} date{'s' if n != 1 else ''}. See you on the court 🥏")
    st.balloons()


# ── Roster tab ──────────────────────────────────────────────────────────────
def roster_tab(sessions: list[dict], signups: list[dict]) -> None:
    for s in sessions:
        roster = going(signups, s["id"])
        counts = {m: sum(r["matchup"] == m for r in roster) for m in MATCHUPS}
        title = f"{session_label(s)} — {format_badge(s)} · {len(roster)} going"
        with st.expander(title, expanded=not is_locked(s) and s is next(
            (x for x in sessions if not is_locked(x)), None
        )):
            if s["notes"]:
                st.caption(s["notes"])
            c1, c2, c3 = st.columns(3)
            c1.metric("WMP", counts["WMP"])
            c2.metric("MMP", counts["MMP"])
            c3.metric("Either", counts["Either"])
            if s["court_cost"] and roster:
                st.caption(
                    f"Court cost {money(s['court_cost'])} → about "
                    f"**{money(float(s['court_cost']) / len(roster))}/person** if split evenly (PWYC)."
                )
            if roster:
                st.write(", ".join(f"{r['player_name']} ({r['matchup']})" for r in roster))
            else:
                st.write("_No one yet._")


# ── Admin tab ───────────────────────────────────────────────────────────────
def format_planner(sessions: list[dict], signups: list[dict]) -> None:
    """Per-date WMP/MMP counts with a suggested format, to help pick WMP-only dates."""
    wmp_min = int(st.secrets.get("WMP_ONLY_MIN", 8))     # WMP bodies needed for a WMP-only night
    mixed_min = int(st.secrets.get("MIXED_MIN_EACH", 4))  # min of each matchup for a mixed night
    st.subheader("Format planner")
    st.caption(
        f"Rule of thumb: WMP-only needs ≥ {wmp_min} WMP (4v4 + subs); mixed needs ≥ {mixed_min} of each. "
        "'Either' players count toward whichever side is short. Change thresholds in secrets."
    )
    out = []
    for s in sessions:
        r = going(signups, s["id"])
        w = sum(x["matchup"] == "WMP" for x in r)
        m = sum(x["matchup"] == "MMP" for x in r)
        e = sum(x["matchup"] == "Either" for x in r)
        if s["is_cancelled"]:
            hint = "—"
        elif w + e >= wmp_min and m + e < mixed_min:
            hint = "WMP-only (not enough MMP for mixed)"
        elif w + e >= wmp_min:
            hint = "WMP-only possible"
        elif min(w + e, m + e) >= mixed_min:
            hint = "Mixed"
        else:
            hint = "Low numbers — recruit or combine"
        out.append(
            {"Date": session_label(s), "Set to": format_badge(s), "WMP": w, "MMP": m,
             "Either": e, "Total": len(r), "Suggestion": hint}
        )
    st.dataframe(pd.DataFrame(out), hide_index=True, width="stretch")


def admin_tab(sessions: list[dict], signups: list[dict], feedback: list[dict]) -> None:
    if not st.session_state.get("is_admin"):
        pw = st.text_input("Admin password", type="password")
        if pw:
            if hmac.compare_digest(pw, st.secrets["ADMIN_PASSWORD"]):
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Wrong password.")
        return

    client = db()
    format_planner(sessions, signups)
    st.divider()
    labels = {s["id"]: f"{session_label(s)} — {format_badge(s)}" for s in sessions}
    upcoming = next((s["id"] for s in sessions if datetime.now(TZ).date() <= date.fromisoformat(s["session_date"])), sessions[-1]["id"])
    sid = st.selectbox(
        "Session", list(labels), index=list(labels).index(upcoming), format_func=labels.get
    )
    s = next(x for x in sessions if x["id"] == sid)
    rows = [r for r in signups if r["session_id"] == sid]

    # Money summary
    attended = [r for r in rows if r["attended"]]
    collected = sum(float(r["amount_paid"] or 0) for r in rows)
    unpaid = [r["player_name"] for r in attended if not r["paid"]]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signed up", len([r for r in rows if r["status"] == "going"]))
    c2.metric("Checked in", len(attended))
    c3.metric("Collected", money(collected))
    c4.metric(
        "vs. court cost",
        money(s["court_cost"]) if s["court_cost"] else "—",
        delta=money(collected - float(s["court_cost"])) if s["court_cost"] else None,
    )
    if unpaid:
        st.warning("Checked in but not marked paid: " + ", ".join(unpaid))
    if s["format"] == "wmp":
        mmp = [r["player_name"] for r in rows if r["status"] == "going" and r["matchup"] == "MMP"]
        if mmp:
            st.warning(
                "This date is WMP-only but these MMP players are signed up (signed up before the "
                "format was set?) — give them a heads-up: " + ", ".join(mmp)
            )

    # Check-in sheet
    st.subheader("Check-in & payments")
    if rows:
        df = pd.DataFrame(rows)[
            ["id", "player_name", "matchup", "status", "is_walk_in", "attended", "paid", "amount_paid", "payment_method"]
        ]
        df["amount_paid"] = df["amount_paid"].astype(float)
        df["payment_method"] = df["payment_method"].fillna("")
        df = df.sort_values(["status", "player_name"], key=lambda c: c.str.lower() if c.dtype == object else c)
        edited = st.data_editor(
            df,
            key=f"editor-{sid}",
            hide_index=True,
            width="stretch",
            disabled=["id", "player_name", "is_walk_in"],
            column_config={
                "id": None,
                "player_name": "Player",
                "matchup": st.column_config.SelectboxColumn("Matchup", options=MATCHUPS),
                "status": st.column_config.SelectboxColumn("Status", options=["going", "cancelled"]),
                "is_walk_in": st.column_config.CheckboxColumn("Walk-in"),
                "attended": st.column_config.CheckboxColumn("Here"),
                "paid": st.column_config.CheckboxColumn("Paid"),
                "amount_paid": st.column_config.NumberColumn("Amount", min_value=0, step=1, format="$%.2f"),
                "payment_method": st.column_config.SelectboxColumn("Method", options=PAYMENT_METHODS),
            },
        )
        if st.button("Save check-in", type="primary"):
            before = df.set_index("id")
            after = edited.set_index("id")
            changed = 0
            for rid, new in after.iterrows():
                old = before.loc[rid]
                diff = {}
                for col in ["matchup", "status", "attended", "paid", "amount_paid", "payment_method"]:
                    if new[col] != old[col]:
                        val = new[col]
                        if col in ("attended", "paid"):
                            val = bool(val)
                        elif col == "amount_paid":
                            val = float(val or 0)
                        elif col == "payment_method":
                            val = val or None
                        diff[col] = val
                if diff.get("amount_paid", 0) > 0 and "paid" not in diff and not old["paid"]:
                    diff["paid"] = True  # entering an amount implies paid
                if diff:
                    client.table("mini_signups").update(diff).eq("id", int(rid)).execute()
                    changed += 1
            refresh()
            st.success(f"Saved {changed} change{'s' if changed != 1 else ''}.")
            st.rerun()
    else:
        st.write("_No signups for this session yet._")

    with st.expander("➕ Add a walk-in"):
        with st.form(f"walkin-{sid}", clear_on_submit=True):
            w_name = st.text_input("Name").strip()
            w_match = st.radio("Matchup", MATCHUPS, horizontal=True)
            w_amt = st.number_input("Amount paid", min_value=0.0, step=1.0)
            w_method = st.selectbox("Method", PAYMENT_METHODS)
            if st.form_submit_button("Add walk-in") and w_name:
                client.table("mini_signups").upsert(
                    {
                        "session_id": sid,
                        "player_name": w_name,
                        "player_key": player_key(w_name),
                        "matchup": w_match,
                        "status": "going",
                        "is_walk_in": True,
                        "attended": True,
                        "paid": w_amt > 0,
                        "amount_paid": w_amt,
                        "payment_method": w_method or None,
                    },
                    on_conflict="session_id,player_key",
                ).execute()
                refresh()
                st.rerun()

    with st.expander("⚙️ Session settings"):
        with st.form(f"settings-{sid}"):
            fmt_keys = list(FORMAT_LABELS)
            new_fmt = st.radio(
                "Format", fmt_keys, index=fmt_keys.index(s["format"]),
                format_func=FORMAT_LABELS.get, horizontal=True,
            )
            new_cap = st.number_input("Capacity (0 = no cap)", min_value=0, value=s["capacity"] or 0, step=1)
            new_cost = st.number_input(
                "Court cost ($)", min_value=0.0, value=float(s["court_cost"] or 0), step=5.0
            )
            new_notes = st.text_input("Note shown on roster", value=s["notes"] or "")
            new_cancel = st.checkbox("Session cancelled", value=s["is_cancelled"])
            if st.form_submit_button("Save settings"):
                client.table("mini_sessions").update(
                    {
                        "format": new_fmt,
                        "capacity": int(new_cap) or None,
                        "court_cost": new_cost or None,
                        "notes": new_notes.strip() or None,
                        "is_cancelled": new_cancel,
                    }
                ).eq("id", sid).execute()
                refresh()
                st.rerun()

    # Season overview
    st.subheader("Season overview")
    if signups:
        all_df = pd.DataFrame(signups)
        date_by_id = {x["id"]: date.fromisoformat(x["session_date"]).strftime("%b %-d") for x in sessions}
        all_df["date"] = all_df["session_id"].map(date_by_id)
        active = all_df[all_df["status"] == "going"]
        grid = active.pivot_table(index="player_name", columns="date", values="id", aggfunc="count", fill_value=0)
        grid = grid.reindex(columns=[d for d in date_by_id.values() if d in grid.columns])
        grid = grid.map(lambda v: "✅" if v else "") if hasattr(grid, "map") else grid.applymap(lambda v: "✅" if v else "")
        paid = all_df.groupby("player_name")["amount_paid"].apply(lambda c: c.astype(float).sum())
        grid["Dates"] = active.groupby("player_name").size()
        grid["Paid total"] = paid.reindex(grid.index).fillna(0).map(money)
        st.dataframe(grid, width="stretch")
        total = all_df["amount_paid"].astype(float).sum()
        cost = sum(float(x["court_cost"] or 0) for x in sessions if not x["is_cancelled"])
        st.caption(f"Collected all season: **{money(total)}**" + (f" of {money(cost)} court cost" if cost else ""))
        st.download_button(
            "Download all signups (CSV)",
            all_df.drop(columns=["player_key"]).to_csv(index=False),
            file_name="mini_signups.csv",
            mime="text/csv",
        )

    st.subheader("Format feedback")
    if feedback:
        fb = pd.DataFrame(feedback)
        tally = fb["preference"].map(PREFERENCES).value_counts()
        st.bar_chart(tally, horizontal=True)
        st.dataframe(
            fb.assign(preference=fb["preference"].map(PREFERENCES))[["player_name", "preference", "comments"]],
            hide_index=True,
            width="stretch",
        )
    else:
        st.write("_No feedback yet._")

    if st.button("Log out"):
        st.session_state.is_admin = False
        st.rerun()


# ── Main ────────────────────────────────────────────────────────────────────
def main() -> None:
    st.title("🥏 Indoor Mini Signups")
    sessions, signups, feedback = load_sessions(), load_signups(), load_feedback()
    if not sessions:
        st.error("No sessions found — run supabase/schema.sql in your Supabase project first.")
        return
    t1, t2, t3 = st.tabs(["Sign up", "Who's going", "Admin"])
    with t1:
        signup_tab(sessions, signups, feedback)
    with t2:
        roster_tab(sessions, signups)
    with t3:
        admin_tab(sessions, signups, feedback)


main()
