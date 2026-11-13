-- Indoor Mini signups: run this once in the Supabase SQL editor of a NEW/separate project.
-- Tables are prefixed `mini_` so they won't collide with anything else.

-- ── Sessions ────────────────────────────────────────────────────────────────
create table if not exists public.mini_sessions (
    id            bigint generated always as identity primary key,
    session_date  date        not null unique,
    start_time    time        not null default '21:30',
    end_time      time        not null default '22:30',
    location      text        not null default 'ComEd',
    format        text        not null default 'tbd'
                  check (format in ('tbd', 'mixed', 'wmp')),
    capacity      integer     check (capacity is null or capacity > 0),
    court_cost    numeric(8,2) check (court_cost is null or court_cost >= 0),
    is_cancelled  boolean     not null default false,
    notes         text,
    created_at    timestamptz not null default now()
);

-- ── Signups (one row per player per session; payment collected at the session) ─
create table if not exists public.mini_signups (
    id              bigint generated always as identity primary key,
    session_id      bigint      not null references public.mini_sessions(id) on delete cascade,
    player_name     text        not null,
    player_key      text        not null,          -- lower-cased email (walk-ins without email: "walkin:<name>")
    contact         text,                           -- email as typed
    matchup         text        not null
                    check (matchup in ('WMP', 'MMP', 'Either')),
    status          text        not null default 'going'
                    check (status in ('going', 'cancelled')),
    is_walk_in      boolean     not null default false,
    attended        boolean     not null default false,
    paid            boolean     not null default false,
    amount_paid     numeric(8,2) not null default 0 check (amount_paid >= 0),
    payment_method  text,                           -- Venmo / Zelle / Cash / ...
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (session_id, player_key)
);

create index if not exists mini_signups_session_idx on public.mini_signups (session_id);

create or replace function public.mini_touch_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at := now();
    return new;
end $$;

drop trigger if exists mini_signups_touch on public.mini_signups;
create trigger mini_signups_touch
    before update on public.mini_signups
    for each row execute function public.mini_touch_updated_at();

-- ── Feedback on mixed vs WMP-only dates ─────────────────────────────────────
create table if not exists public.mini_feedback (
    id            bigint generated always as identity primary key,
    player_name   text        not null,
    player_key    text        not null unique,   -- lower-cased email
    preference    text        not null
                  check (preference in ('mixed', 'wmp', 'some_of_each', 'no_preference')),
    comments      text,
    updated_at    timestamptz not null default now()
);

-- ── Security ────────────────────────────────────────────────────────────────
-- RLS on with no policies = the public anon key can't read or write anything.
-- The Streamlit app runs server-side with the service_role key, which bypasses RLS.
alter table public.mini_sessions enable row level security;
alter table public.mini_signups  enable row level security;
alter table public.mini_feedback enable row level security;

-- ── Seed the five Wednesdays ────────────────────────────────────────────────
insert into public.mini_sessions (session_date) values
    ('2026-11-18'),
    ('2026-11-25'),
    ('2026-12-02'),
    ('2026-12-09'),
    ('2026-12-16')
on conflict (session_date) do nothing;
