-- Ejecutar una vez en Supabase: SQL Editor -> New query -> Run

create table if not exists public.historial_inventario (
  id        bigint generated always as identity primary key,
  objeto    text        not null,
  uid       text        not null,
  evento    text        not null check (evento in ('RETIRADO', 'DEVUELTO')),
  lector    int,
  creado_en timestamptz not null default now()
);

create index if not exists historial_inventario_creado_en_idx
  on public.historial_inventario (creado_en desc);

-- Seguridad: la anon key solo puede insertar y leer, no modificar ni borrar
alter table public.historial_inventario enable row level security;

create policy "anon puede insertar"
  on public.historial_inventario for insert
  to anon
  with check (true);

create policy "anon puede leer"
  on public.historial_inventario for select
  to anon
  using (true);
