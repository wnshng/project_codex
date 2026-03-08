create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  created_at timestamptz not null default now()
);

create table if not exists public.clothing_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  category text not null check (category in ('top','bottom','outer','dress','shoes','bag','accessory','unknown')),
  subcategory text,
  brand text,
  color_hex text not null,
  material text,
  season text[] not null default '{}',
  style_tags text[] not null default '{}',
  warmth_level int not null default 3 check (warmth_level between 1 and 5),
  created_at timestamptz not null default now()
);

create index if not exists idx_clothing_items_user_id on public.clothing_items(user_id);
create index if not exists idx_clothing_items_category on public.clothing_items(category);

create table if not exists public.item_images (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.clothing_items(id) on delete cascade,
  storage_path text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.style_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  personal_color text,
  preferred_styles text[] not null default '{}',
  updated_at timestamptz not null default now()
);

create table if not exists public.outfit_recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  item_ids uuid[] not null,
  reason text not null,
  score numeric(5,3) not null,
  created_at timestamptz not null default now()
);

alter table public.users enable row level security;
alter table public.clothing_items enable row level security;
alter table public.item_images enable row level security;
alter table public.style_profiles enable row level security;
alter table public.outfit_recommendations enable row level security;

create policy if not exists users_self_select
  on public.users for select
  using (auth.uid() = id);

create policy if not exists clothing_items_owner_all
  on public.clothing_items for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy if not exists item_images_owner_all
  on public.item_images for all
  using (
    exists (
      select 1 from public.clothing_items ci
      where ci.id = item_images.item_id and ci.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.clothing_items ci
      where ci.id = item_images.item_id and ci.user_id = auth.uid()
    )
  );

create policy if not exists style_profiles_owner_all
  on public.style_profiles for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy if not exists outfit_recommendations_owner_all
  on public.outfit_recommendations for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
