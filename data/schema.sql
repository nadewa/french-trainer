-- Run this once in your Supabase project's SQL editor to enable cloud sync.
-- See README.md "Cloud sync setup" for the full walkthrough.

create table if not exists progress (
  user_id uuid references auth.users(id) on delete cascade primary key,
  state jsonb not null,
  updated_at timestamptz not null default now()
);

alter table progress enable row level security;

create policy "Users can view their own progress"
  on progress for select
  using (auth.uid() = user_id);

create policy "Users can insert their own progress"
  on progress for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own progress"
  on progress for update
  using (auth.uid() = user_id);
