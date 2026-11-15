-- =====================================================================
--  INVENTARIO RFID - Esquema de Supabase
--
--  Ejecutar completo en: SQL Editor -> New query -> Run
--  Se puede ejecutar varias veces: no borra datos existentes.
--
--  Tablas
--    dispositivos  Un ESP32 (stand) por fila. Guarda su ultimo latido.
--    recursos      Catalogo + que tag RFID lleva cada recurso + en que
--                  lector va + donde esta ahora mismo.
--    eventos       Historial. El ESP32 solo escribe aqui.
--
--  El ESP32 manda eventos "en bruto" (UID + numero de lector). Un trigger
--  los traduce a recurso, decide si esta en el lugar correcto y actualiza
--  la tabla recursos. Por eso el mapeo tag <-> recurso <-> lector se
--  cambia aqui (Table Editor -> recursos) sin tocar el ESP32.
--
--  La tabla antigua historial_inventario ya no se usa. Este script no la
--  toca; se puede borrar a mano cuando ya no haga falta.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. DISPOSITIVOS
-- ---------------------------------------------------------------------

create table if not exists public.dispositivos (
  id            text primary key,          -- igual a DISPOSITIVO_ID del sketch
  nombre        text,
  firmware      text,
  ip            text,
  rssi          int,                       -- senal WiFi en dBm
  arranque      int,                       -- contador de encendidos
  ultimo_latido timestamptz
);


-- ---------------------------------------------------------------------
-- 2. RECURSOS
-- ---------------------------------------------------------------------

-- Deja un UID en formato canonico: hexadecimal, mayusculas, sin separadores.
-- Acepta 'AF91D01C', 'af 91 d0 1c', 'AF:91:D0:1C' y '0xAF, 0x91, 0xD0, 0x1C'.
create or replace function public.normalizar_uid(p text)
returns text
language sql
immutable
as $$
  select nullif(
    upper(regexp_replace(regexp_replace(coalesce(p, ''), '0[xX]', '', 'g'), '[^0-9A-Fa-f]', '', 'g')),
    ''
  )
$$;

create table if not exists public.recursos (
  -- Catalogo
  id          text primary key,            -- 'ACT-004'
  nombre      text not null,
  categoria   text,
  tipo        text,
  gabinete    text,
  estante     int,
  posicion    int,
  en_revision boolean not null default false,

  -- Mapeo: ESTO ES LO QUE SE EDITA para cambiar que objeto va en que
  -- lector. El ESP32 lo vuelve a leer cada 10 s.
  uid_tag        text unique,              -- UID del tag pegado al recurso
  dispositivo_id text references public.dispositivos (id),
  lector         int,                      -- lector asignado (uno por objeto); vacio = cualquiera

  -- Estado en vivo: lo escribe el trigger, no editar a mano
  presente           boolean not null default false,
  dispositivo_actual text,
  lector_actual      int,
  actualizado_en     timestamptz,

  -- Indicador luminoso: el LED del lector se enciende hasta esta hora
  senalizar_hasta timestamptz,

  -- Un UID MIFARE tiene 4, 7 o 10 bytes
  constraint recursos_uid_tag_valido
    check (uid_tag is null or (uid_tag ~ '^[0-9A-F]+$' and length(uid_tag) in (8, 14, 20)))
);

create index if not exists recursos_dispositivo_idx
  on public.recursos (dispositivo_id);

-- Un solo objeto correcto por lector.
--
-- La regla se comprueba al final de cada transaccion, no en cada UPDATE.
-- Asi una funcion futura puede intercambiar dos objetos de lector en una
-- sola transaccion sin chocar a mitad de camino:
--   begin;
--   update recursos set lector = 2 where id = 'ACT-004';
--   update recursos set lector = 1 where id = 'ACT-007';
--   commit;
do $$
declare
  repetidos text;
begin
  -- Quien ejecuto la version anterior de este script tiene dos objetos en
  -- el lector 1. Se pasan al reparto nuevo, solo si siguen sin tocar.
  if exists (select 1 from public.recursos
              where id = 'ACT-007' and uid_tag = '15F9DD00' and dispositivo_id = 'stand-01' and lector = 1)
     and exists (select 1 from public.recursos
              where id = 'ACT-001' and uid_tag = '06F123CE' and dispositivo_id = 'stand-01' and lector = 2)
     and not exists (select 1 from public.recursos
              where dispositivo_id = 'stand-01' and lector = 3)
  then
    update public.recursos set lector = 3 where id = 'ACT-001';
    update public.recursos set lector = 2 where id = 'ACT-007';
  end if;

  if not exists (select 1 from pg_constraint where conname = 'recursos_lector_valido') then
    alter table public.recursos
      add constraint recursos_lector_valido
      check (lector is null or (lector >= 1 and dispositivo_id is not null));
  end if;

  if not exists (select 1 from pg_constraint where conname = 'recursos_un_objeto_por_lector') then
    select string_agg(format('%s lector %s: %s', dispositivo_id, lector, ids), '; ')
      into repetidos
      from (select dispositivo_id, lector, string_agg(id, ', ' order by id) ids
              from public.recursos
             where dispositivo_id is not null and lector is not null
             group by 1, 2
            having count(*) > 1) d;

    if repetidos is not null then
      raise exception 'Hay lectores con mas de un objeto asignado: %', repetidos
        using hint = 'Deja un solo recurso por lector (columna lector en recursos) y vuelve a ejecutar el script.';
    end if;

    alter table public.recursos
      add constraint recursos_un_objeto_por_lector
      unique (dispositivo_id, lector)
      deferrable initially deferred;
  end if;
end
$$;

create or replace function public.recursos_antes_guardar()
returns trigger
language plpgsql
as $$
begin
  new.uid_tag := public.normalizar_uid(new.uid_tag);
  return new;
end
$$;

drop trigger if exists recursos_antes_guardar on public.recursos;
create trigger recursos_antes_guardar
  before insert or update of uid_tag on public.recursos
  for each row execute function public.recursos_antes_guardar();


-- ---------------------------------------------------------------------
-- 3. EVENTOS
-- ---------------------------------------------------------------------
--
--  Lo que manda el ESP32:
--    INICIO    El ESP32 acaba de encender (sin uid ni lector).
--    PRESENTE  Tag que ya estaba sobre un lector al encender.
--    DEVUELTO  Un tag aparecio sobre un lector.
--    RETIRADO  Un tag desaparecio de un lector.
--
--  Lo que rellena el trigger:
--    recurso_id   A que recurso corresponde el UID (vacio si es desconocido).
--    resultado    OK               tag conocido en su lector
--                 LUGAR_INCORRECTO tag conocido en otro lector o stand
--                 DESCONOCIDO      el UID no esta en la tabla recursos
--    ocurrido_en  Hora real del evento.

create table if not exists public.eventos (
  id             bigint generated always as identity primary key,

  dispositivo_id text   not null,
  arranque       int    not null,
  seq            int    not null,
  evento         text   not null check (evento in ('INICIO', 'PRESENTE', 'DEVUELTO', 'RETIRADO')),
  uid            text,
  lector         int,
  antiguedad_ms  bigint,                   -- hace cuanto ocurrio, segun el ESP32

  recurso_id     text references public.recursos (id),
  resultado      text,
  ocurrido_en    timestamptz,
  recibido_en    timestamptz not null default now(),

  -- Un reintento del ESP32 no puede duplicar un evento
  constraint eventos_sin_duplicados unique (dispositivo_id, arranque, seq)
);

create index if not exists eventos_ocurrido_en_idx on public.eventos (ocurrido_en desc);
create index if not exists eventos_recurso_idx     on public.eventos (recurso_id, ocurrido_en desc);

create or replace function public.procesar_evento()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  r public.recursos%rowtype;
begin
  -- Estos campos los decide el servidor, venga lo que venga del cliente.
  new.recibido_en := now();
  new.ocurrido_en := now() - make_interval(secs => greatest(coalesce(new.antiguedad_ms, 0), 0) / 1000.0);
  new.uid         := public.normalizar_uid(new.uid);
  new.recurso_id  := null;
  new.resultado   := null;

  -- Un dispositivo nuevo se registra solo.
  insert into dispositivos (id, arranque, ultimo_latido)
  values (new.dispositivo_id, new.arranque, now())
  on conflict (id) do update
    set arranque = excluded.arranque,
        ultimo_latido = excluded.ultimo_latido;

  -- Al encender se olvida lo que este stand tenia; los eventos PRESENTE
  -- que llegan a continuacion vuelven a marcar lo que si esta.
  if new.evento = 'INICIO' then
    update recursos
       set presente = false,
           dispositivo_actual = null,
           lector_actual = null,
           actualizado_en = new.ocurrido_en
     where dispositivo_actual = new.dispositivo_id;
    return new;
  end if;

  if new.uid is null or new.lector is null then
    raise exception 'El evento % necesita uid y lector', new.evento
      using errcode = '22023';
  end if;

  select * into r from recursos where uid_tag = new.uid;

  if not found then
    new.resultado := 'DESCONOCIDO';
    return new;
  end if;

  new.recurso_id := r.id;

  if new.evento = 'RETIRADO' then
    new.resultado := 'OK';
    -- Solo si sigue registrado en ese lector: al mover un recurso de un
    -- lector a otro, el DEVUELTO del nuevo llega antes que este RETIRADO.
    update recursos
       set presente = false,
           dispositivo_actual = null,
           lector_actual = null,
           actualizado_en = new.ocurrido_en,
           senalizar_hasta = null
     where id = r.id
       and dispositivo_actual = new.dispositivo_id
       and lector_actual = new.lector;
  else
    -- PRESENTE o DEVUELTO
    if r.dispositivo_id = new.dispositivo_id and (r.lector is null or r.lector = new.lector) then
      new.resultado := 'OK';
    else
      new.resultado := 'LUGAR_INCORRECTO';
    end if;

    update recursos
       set presente = true,
           dispositivo_actual = new.dispositivo_id,
           lector_actual = new.lector,
           actualizado_en = new.ocurrido_en,
           senalizar_hasta = case when new.resultado = 'OK' then null else senalizar_hasta end
     where id = r.id;
  end if;

  return new;
end
$$;

drop trigger if exists eventos_procesar on public.eventos;
create trigger eventos_procesar
  before insert on public.eventos
  for each row execute function public.procesar_evento();


-- ---------------------------------------------------------------------
-- 4. FUNCIONES Y VISTAS
-- ---------------------------------------------------------------------

-- Latido: el ESP32 la llama cada 30 s para decir "sigo vivo".
create or replace function public.latido(
  p_dispositivo text,
  p_arranque    int,
  p_firmware    text,
  p_ip          text,
  p_rssi        int
)
returns void
language sql
security definer
set search_path = public
as $$
  insert into dispositivos (id, arranque, firmware, ip, rssi, ultimo_latido)
  values (p_dispositivo, p_arranque, p_firmware, p_ip, p_rssi, now())
  on conflict (id) do update
    set arranque = excluded.arranque,
        firmware = excluded.firmware,
        ip = excluded.ip,
        rssi = excluded.rssi,
        ultimo_latido = excluded.ultimo_latido;
$$;

-- Indicador luminoso: la app la llama para encender el LED del lector
-- donde va un recurso. Con p_segundos = 0 lo apaga.
--   supabase.rpc('senalizar', { p_recurso: 'ACT-004' })
create or replace function public.senalizar(p_recurso text, p_segundos int default 30)
returns void
language sql
security definer
set search_path = public
as $$
  update recursos
     set senalizar_hasta = now() + make_interval(secs => least(greatest(coalesce(p_segundos, 30), 0), 300))
   where id = p_recurso;
$$;

-- Lectores cuyo LED debe estar encendido ahora. El ESP32 la lee cada 2 s.
create or replace view public.senales
with (security_invoker = true)
as
  select dispositivo_id, lector
    from public.recursos
   where senalizar_hasta > now()
     and dispositivo_id is not null
     and lector is not null;

-- Estado de cada stand: en linea si hubo latido en los ultimos 90 s.
create or replace view public.dispositivos_estado
with (security_invoker = true)
as
  select id,
         nombre,
         ultimo_latido,
         coalesce(ultimo_latido > now() - interval '90 seconds', false) as en_linea
    from public.dispositivos;


-- ---------------------------------------------------------------------
-- 5. SEGURIDAD
-- ---------------------------------------------------------------------
--  Con la anon key se puede: leer las tres tablas, insertar eventos y
--  llamar a latido() y senalizar(). No se puede modificar ni borrar nada.
--  El mapeo se edita desde el panel de Supabase, que no pasa por estas reglas.

alter table public.dispositivos enable row level security;
alter table public.recursos     enable row level security;
alter table public.eventos      enable row level security;

drop policy if exists "leer dispositivos" on public.dispositivos;
create policy "leer dispositivos" on public.dispositivos
  for select to anon, authenticated using (true);

drop policy if exists "leer recursos" on public.recursos;
create policy "leer recursos" on public.recursos
  for select to anon, authenticated using (true);

drop policy if exists "leer eventos" on public.eventos;
create policy "leer eventos" on public.eventos
  for select to anon, authenticated using (true);

drop policy if exists "insertar eventos" on public.eventos;
create policy "insertar eventos" on public.eventos
  for insert to anon, authenticated with check (true);

grant select on public.dispositivos, public.recursos, public.eventos to anon, authenticated;
grant select on public.senales, public.dispositivos_estado to anon, authenticated;
grant insert on public.eventos to anon, authenticated;
grant execute on function public.latido(text, int, text, text, int) to anon, authenticated;
grant execute on function public.senalizar(text, int) to anon, authenticated;


-- ---------------------------------------------------------------------
-- 6. TIEMPO REAL
-- ---------------------------------------------------------------------
--  Permite que la app se entere al instante de cada cambio.

do $$
declare
  t text;
begin
  foreach t in array array['eventos', 'recursos', 'dispositivos'] loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception
      when duplicate_object then null;   -- ya estaba
      when undefined_object then null;   -- no existe la publicacion
    end;
  end loop;
end
$$;


-- ---------------------------------------------------------------------
-- 7. DATOS INICIALES
-- ---------------------------------------------------------------------
--  El catalogo es el de la maqueta de la app. Los tres tags son los que
--  estaban escritos en el sketch original, uno por lector; a que recurso
--  corresponde cada uno es una suposicion: corregirlo en
--  Table Editor -> recursos.

insert into public.dispositivos (id, nombre)
values ('stand-01', 'Stand de electronica')
on conflict (id) do nothing;

insert into public.recursos
  (id, nombre, categoria, tipo, gabinete, estante, posicion, en_revision, uid_tag, dispositivo_id, lector)
values
  ('ACT-004', 'Multímetro digital #04',     'Medición eléctrica', 'Equipo de medición', 'A', 2, 3, false, 'AF91D01C', 'stand-01', 1),
  ('ACT-007', 'Kit de electrónica #07',     'Kits de práctica',   'Kit',                'B', 1, 1, false, '15F9DD00', 'stand-01', 2),
  ('ACT-001', 'Generador de señales #01',   'Medición eléctrica', 'Equipo de medición', 'A', 1, 4, false, '06F123CE', 'stand-01', 3),
  ('ACT-002', 'Osciloscopio #02',           'Medición eléctrica', 'Equipo de medición', 'A', 1, 2, false, null, null, null),
  ('ACT-003', 'Fuente de alimentación #03', 'Alimentación',       'Fuente',             'A', 3, 2, false, null, null, null),
  ('ACT-005', 'Estación de soldadura #05',  'Herramientas',       'Herramienta',        'C', 1, 2, true,  null, null, null),
  ('ACT-006', 'Pinza amperimétrica #06',    'Medición eléctrica', 'Equipo de medición', 'A', 2, 1, false, null, null, null),
  ('ACT-008', 'Kit Arduino #08',            'Kits de práctica',   'Kit',                'B', 2, 3, false, null, null, null),
  ('ACT-009', 'Protoboard #09',             'Kits de práctica',   'Kit',                'B', 2, 4, false, null, null, null),
  ('ACT-010', 'Analizador lógico #10',      'Medición eléctrica', 'Equipo de medición', 'A', 3, 1, false, null, null, null),
  ('ACT-011', 'Cautín #11',                 'Herramientas',       'Herramienta',        'C', 1, 3, false, null, null, null),
  ('ACT-012', 'Fuente dual #12',            'Alimentación',       'Fuente',             'A', 3, 4, false, null, null, null)
on conflict (id) do nothing;
