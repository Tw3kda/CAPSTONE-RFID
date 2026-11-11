// =====================================================
//  INVENTARIO INTELIGENTE RFID  -  ESP32
//  3 lectores RC522 + pagina web en vivo + historial en Supabase
// =====================================================
//
//  Librerias (Gestor de librerias de Arduino):
//    - RFID_MFRC522v2       (GithubCommunity)
//    - ESP Async WebServer  (ESP32Async)
//    - Async TCP            (ESP32Async)
//
//  CABLEADO
//  --------
//  Bus SPI compartido por los 3 lectores (VSPI por defecto):
//    SCK  -> GPIO 18
//    MISO -> GPIO 19
//    MOSI -> GPIO 23
//    3.3V y GND comunes (el RC522 NO tolera 5V)
//    RST  -> sin conectar (o a 3.3V)
//
//  Cada lector tiene su propio SDA/SS:
//    Lector 1 SDA -> GPIO 5    (el que ya tenias)
//    Lector 2 SDA -> GPIO 25   (nuevo)
//    Lector 3 SDA -> GPIO 26   (nuevo)
//
//  LEDs (sin cambios):
//    LED_VERDE -> GPIO 22   Objeto 1 presente
//    LED_NUEVO -> GPIO 17   Objeto 2 presente
//    LED_ROJO  -> GPIO 4    Falta al menos un objeto
// =====================================================

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ESPmDNS.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>

// =========================
// CONFIGURACION  (EDITAR)
// =========================

const char* WIFI_SSID = "TU_WIFI";
const char* WIFI_PASS = "TU_CLAVE";

// Supabase: Project Settings -> API
const char* SUPABASE_URL   = "https://TU-PROYECTO.supabase.co";
const char* SUPABASE_KEY   = "TU_ANON_KEY";            // anon / publishable (NO la service_role)
const char* SUPABASE_TABLA = "historial_inventario";

// =========================
// PINES LED (sin cambios)
// =========================

#define LED_VERDE 22
#define LED_NUEVO 17
#define LED_ROJO  4

// =========================
// LECTORES RC522
// =========================

#define SS_LECTOR_1 5     // ya utilizado
#define SS_LECTOR_2 25    // nuevo
#define SS_LECTOR_3 26    // nuevo

MFRC522DriverPinSimple ss1(SS_LECTOR_1);
MFRC522DriverPinSimple ss2(SS_LECTOR_2);
MFRC522DriverPinSimple ss3(SS_LECTOR_3);

MFRC522DriverSPI driver1{ss1};
MFRC522DriverSPI driver2{ss2};
MFRC522DriverSPI driver3{ss3};

MFRC522 rc1{driver1};
MFRC522 rc2{driver2};
MFRC522 rc3{driver3};

MFRC522* lectores[] = { &rc1, &rc2, &rc3 };
const byte   PINES_SS[] = { SS_LECTOR_1, SS_LECTOR_2, SS_LECTOR_3 };
const int    NUM_LECTORES = 3;

// =========================
// CATALOGO DE OBJETOS
// =========================
// Se reutilizan los UID de las tarjetas que ya tenias.
// Para agregar otro objeto, anade una linea (ledPin = -1 si no tiene LED).
// Los tags desconocidos aparecen en la web y en el Serial con su UID.

struct Objeto {
  const char* nombre;
  byte uid[4];
  int  ledPin;
  // --- estado ---
  bool presente;
  int  lector;                 // indice del ultimo lector donde se vio
  bool visto;
  unsigned long ultimaVez;
};

Objeto objetos[] = {
  { "Objeto 1", { 0xAF, 0x91, 0xD0, 0x1C }, LED_VERDE, false, -1, false, 0 },
  { "Objeto 2", { 0x15, 0xF9, 0xDD, 0x00 }, LED_NUEVO, false, -1, false, 0 },
  // { "Objeto 3", { 0x00, 0x00, 0x00, 0x00 }, -1,     false, -1, false, 0 },
};
const int NUM_OBJETOS = sizeof(objetos) / sizeof(objetos[0]);

// =========================
// ESTADO DE CADA LECTOR
// =========================

#define VACIO       -1
#define DESCONOCIDO -2

struct EstadoLector {
  int  contenido;              // indice de objeto, VACIO o DESCONOCIDO
  int  ultimoLeido;
  char uidTexto[21];
  bool visto;
  unsigned long ultimaVez;
};

EstadoLector estadoLector[NUM_LECTORES];

// =========================
// CONTROL DE PRESENCIA
// =========================

const unsigned long TIMEOUT        = 700;    // ms sin leer = objeto retirado
const unsigned long TIEMPO_ARRANQUE = 2500;  // ms iniciales sin registrar eventos

// =========================
// WEB
// =========================

AsyncWebServer  server(80);
AsyncEventSource eventos("/eventos");

// =========================
// COLA HACIA SUPABASE
// =========================

struct Evento {
  char objeto[32];
  char uid[12];
  char tipo[10];               // RETIRADO / DEVUELTO
  int  lector;                 // 1..3
};

QueueHandle_t colaEventos;


// =====================================================
// PAGINA WEB
// =====================================================

const char INDEX_HTML[] PROGMEM = R"HTML(
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inventario RFID</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --txt:#e2e8f0; --mut:#94a3b8;
          --ok:#22c55e; --bad:#ef4444; --warn:#f59e0b; --line:#334155; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Segoe UI,Roboto,sans-serif;
         background:var(--bg); color:var(--txt); padding:16px; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  h2 { font-size:1rem; color:var(--mut); margin:24px 0 8px; font-weight:600; }
  #conexion { font-size:.85rem; color:var(--mut); }
  #conexion.on::before  { content:"\25CF "; color:var(--ok); }
  #conexion.off::before { content:"\25CF "; color:var(--bad); }
  .grid { display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); }
  .card { background:var(--card); border-radius:12px; padding:16px;
          border-left:6px solid var(--line); }
  .card.ok   { border-color:var(--ok); }
  .card.bad  { border-color:var(--bad); }
  .card.warn { border-color:var(--warn); }
  .card .tit { font-size:.8rem; color:var(--mut); text-transform:uppercase; letter-spacing:.05em; }
  .card .val { font-size:1.25rem; font-weight:700; margin-top:6px; }
  .card .sub { font-size:.8rem; color:var(--mut); margin-top:4px; font-family:monospace; }
  .tabla { overflow-x:auto; background:var(--card); border-radius:12px; }
  table { width:100%; border-collapse:collapse; font-size:.9rem; }
  th,td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }
  th { color:var(--mut); font-weight:600; }
  .tag { padding:2px 8px; border-radius:99px; font-size:.75rem; font-weight:700; }
  .tag.RETIRADO { background:#7f1d1d; color:#fecaca; }
  .tag.DEVUELTO { background:#14532d; color:#bbf7d0; }
  #histMsg { color:var(--mut); font-size:.85rem; padding:12px; }
</style>
</head>
<body>
  <h1>Inventario RFID</h1>
  <div id="conexion" class="off">Conectando...</div>

  <h2>Objetos</h2>
  <div class="grid" id="objetos"></div>

  <h2>Lectores</h2>
  <div class="grid" id="lectores"></div>

  <h2>Historial (Supabase)</h2>
  <div class="tabla">
    <table>
      <thead><tr><th>Fecha</th><th>Objeto</th><th>Evento</th><th>Lector</th></tr></thead>
      <tbody id="hist"></tbody>
    </table>
    <div id="histMsg">Cargando...</div>
  </div>

<script>
let cfg = null;

function el(tag, cls, txt) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (txt !== undefined) e.textContent = txt;
  return e;
}

function tarjeta(cls, tit, val, sub) {
  const c = el('div', 'card ' + cls);
  c.append(el('div', 'tit', tit), el('div', 'val', val), el('div', 'sub', sub));
  return c;
}

function pintar(st) {
  const o = document.getElementById('objetos');
  o.replaceChildren(...st.objetos.map(x => tarjeta(
    x.presente ? 'ok' : 'bad',
    x.nombre,
    x.presente ? 'Disponible' : 'Prestado',
    x.presente ? 'En lector ' + x.lector : 'UID ' + x.uid)));

  const l = document.getElementById('lectores');
  l.replaceChildren(...st.lectores.map(x => {
    if (x.estado === 'objeto')      return tarjeta('ok',   'Lector ' + x.id, x.nombre, 'UID ' + x.uid);
    if (x.estado === 'desconocido') return tarjeta('warn', 'Lector ' + x.id, 'Tag desconocido', 'UID ' + x.uid);
    return tarjeta('', 'Lector ' + x.id, 'Vacio', '—');
  }));
}

async function cargarEstado() {
  try { pintar(await (await fetch('/api/estado')).json()); } catch (e) {}
}

async function cargarHistorial() {
  const msg = document.getElementById('histMsg');
  try {
    if (!cfg) cfg = await (await fetch('/api/config')).json();
    const r = await fetch(cfg.url + '/rest/v1/' + cfg.tabla +
      '?select=*&order=creado_en.desc&limit=25',
      { headers: { apikey: cfg.key, Authorization: 'Bearer ' + cfg.key } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const filas = await r.json();
    document.getElementById('hist').replaceChildren(...filas.map(f => {
      const tr = el('tr');
      const ev = el('td'); ev.append(el('span', 'tag ' + f.evento, f.evento));
      tr.append(el('td', '', new Date(f.creado_en).toLocaleString()),
                el('td', '', f.objeto), ev,
                el('td', '', f.lector ? 'Lector ' + f.lector : '—'));
      return tr;
    }));
    msg.textContent = filas.length ? '' : 'Sin registros todavia.';
  } catch (e) {
    msg.textContent = 'No se pudo leer Supabase (' + e.message + ').';
  }
}

const con = document.getElementById('conexion');
const es = new EventSource('/eventos');
es.onopen  = () => { con.className = 'on';  con.textContent = 'En vivo'; cargarEstado(); };
es.onerror = () => { con.className = 'off'; con.textContent = 'Sin conexion con el ESP32'; };
es.addEventListener('estado', e => {
  pintar(JSON.parse(e.data));
  setTimeout(cargarHistorial, 2500);   // dar tiempo a que el ESP32 suba el evento
});

cargarEstado();
cargarHistorial();
setInterval(cargarHistorial, 30000);
</script>
</body>
</html>
)HTML";


// =====================================================
// UTILIDADES
// =====================================================

void uidATexto(const byte* uid, byte tam, char* destino, size_t maxLen) {
  size_t pos = 0;
  for (byte i = 0; i < tam && pos + 2 < maxLen; i++) {
    pos += snprintf(destino + pos, maxLen - pos, "%02X", uid[i]);
  }
  destino[pos] = '\0';
}

// Devuelve el indice del objeto con ese UID, o DESCONOCIDO
int buscarObjeto(const byte* uid, byte tam) {
  if (tam != 4) return DESCONOCIDO;          // los tags usados tienen UID de 4 bytes
  for (int i = 0; i < NUM_OBJETOS; i++) {
    if (memcmp(uid, objetos[i].uid, 4) == 0) return i;
  }
  return DESCONOCIDO;
}

String estadoJSON() {
  char uid[12];
  String j = "{\"lectores\":[";

  for (int i = 0; i < NUM_LECTORES; i++) {
    if (i) j += ",";
    j += "{\"id\":" + String(i + 1) + ",";
    int c = estadoLector[i].contenido;
    if (c >= 0) {
      uidATexto(objetos[c].uid, 4, uid, sizeof(uid));
      j += "\"estado\":\"objeto\",\"nombre\":\"" + String(objetos[c].nombre) +
           "\",\"uid\":\"" + uid + "\"}";
    } else if (c == DESCONOCIDO) {
      j += "\"estado\":\"desconocido\",\"uid\":\"" + String(estadoLector[i].uidTexto) + "\"}";
    } else {
      j += "\"estado\":\"vacio\"}";
    }
  }

  j += "],\"objetos\":[";

  for (int i = 0; i < NUM_OBJETOS; i++) {
    if (i) j += ",";
    uidATexto(objetos[i].uid, 4, uid, sizeof(uid));
    j += "{\"nombre\":\"" + String(objetos[i].nombre) + "\",\"uid\":\"" + uid +
         "\",\"presente\":" + (objetos[i].presente ? "true" : "false") +
         ",\"lector\":" + String(objetos[i].lector + 1) + "}";
  }

  j += "]}";
  return j;
}


// =====================================================
// SUPABASE
// =====================================================

// Encola el evento; la subida se hace en otra tarea para no frenar los lectores
void registrarEvento(int idxObjeto, const char* tipo) {
  Evento ev;
  strlcpy(ev.objeto, objetos[idxObjeto].nombre, sizeof(ev.objeto));
  uidATexto(objetos[idxObjeto].uid, 4, ev.uid, sizeof(ev.uid));
  strlcpy(ev.tipo, tipo, sizeof(ev.tipo));
  ev.lector = objetos[idxObjeto].lector + 1;

  Serial.printf("[EVENTO] %s %s (lector %d)\n", ev.objeto, ev.tipo, ev.lector);

  if (xQueueSend(colaEventos, &ev, 0) != pdTRUE) {
    Serial.println("[SUPABASE] Cola llena, evento descartado");
  }
}

bool enviarASupabase(const Evento& ev) {
  WiFiClientSecure cliente;
  cliente.setInsecure();                 // sin validar certificado (simple para prototipo)

  HTTPClient http;
  String url = String(SUPABASE_URL) + "/rest/v1/" + SUPABASE_TABLA;

  if (!http.begin(cliente, url)) return false;

  http.setTimeout(8000);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("apikey", SUPABASE_KEY);
  http.addHeader("Authorization", String("Bearer ") + SUPABASE_KEY);
  http.addHeader("Prefer", "return=minimal");

  String cuerpo = "{\"objeto\":\"" + String(ev.objeto) +
                  "\",\"uid\":\"" + String(ev.uid) +
                  "\",\"evento\":\"" + String(ev.tipo) +
                  "\",\"lector\":" + String(ev.lector) + "}";

  int codigo = http.POST(cuerpo);
  bool ok = (codigo == 201 || codigo == 200 || codigo == 204);

  if (!ok) {
    Serial.printf("[SUPABASE] Error %d: %s\n", codigo, http.getString().c_str());
  }

  http.end();
  return ok;
}

void tareaSupabase(void* parametro) {
  Evento ev;

  for (;;) {
    if (xQueueReceive(colaEventos, &ev, portMAX_DELAY) != pdTRUE) continue;

    bool enviado = false;

    for (int intento = 0; intento < 5 && !enviado; intento++) {
      if (WiFi.status() == WL_CONNECTED) {
        enviado = enviarASupabase(ev);
      }
      if (!enviado) vTaskDelay(pdMS_TO_TICKS(3000));
    }

    Serial.println(enviado ? "[SUPABASE] Evento guardado"
                           : "[SUPABASE] No se pudo guardar el evento");
  }
}


// =====================================================
// LECTURA DE UN LECTOR
// =====================================================

void leerLector(int i) {
  MFRC522* rc = lectores[i];

  byte bufferATQA[2];
  byte bufferSize = sizeof(bufferATQA);

  MFRC522::StatusCode status = rc->PICC_WakeupA(bufferATQA, &bufferSize);

  if (status != MFRC522Constants::STATUS_OK &&
      status != MFRC522Constants::STATUS_COLLISION) {
    return;
  }

  status = rc->PICC_Select(&(rc->uid));
  if (status != MFRC522Constants::STATUS_OK) return;

  unsigned long ahora = millis();
  int idx = buscarObjeto(rc->uid.uidByte, rc->uid.size);

  estadoLector[i].ultimoLeido = idx;
  estadoLector[i].ultimaVez   = ahora;
  estadoLector[i].visto       = true;

  if (idx >= 0) {
    objetos[idx].ultimaVez = ahora;
    objetos[idx].visto     = true;
    objetos[idx].lector    = i;
  } else {
    uidATexto(rc->uid.uidByte, rc->uid.size,
              estadoLector[i].uidTexto, sizeof(estadoLector[i].uidTexto));
  }

  rc->PICC_HaltA();
}


// =====================================================
// LEDs
// =====================================================

void actualizarLEDs() {
  bool faltaAlguno = false;

  for (int i = 0; i < NUM_OBJETOS; i++) {
    if (objetos[i].ledPin >= 0) {
      digitalWrite(objetos[i].ledPin, objetos[i].presente ? HIGH : LOW);
    }
    if (!objetos[i].presente) faltaAlguno = true;
  }

  digitalWrite(LED_ROJO, faltaAlguno ? HIGH : LOW);
}


// =====================================================
// SETUP
// =====================================================

void setup() {

  Serial.begin(115200);

  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_NUEVO, OUTPUT);
  pinMode(LED_ROJO, OUTPUT);

  digitalWrite(LED_VERDE, LOW);
  digitalWrite(LED_NUEVO, LOW);
  digitalWrite(LED_ROJO, HIGH);

  // Todos los SS en HIGH antes de iniciar, para que no hablen a la vez
  for (int i = 0; i < NUM_LECTORES; i++) {
    pinMode(PINES_SS[i], OUTPUT);
    digitalWrite(PINES_SS[i], HIGH);
  }

  for (int i = 0; i < NUM_LECTORES; i++) {
    estadoLector[i] = { VACIO, VACIO, "", false, 0 };
    lectores[i]->PCD_Init();
    delay(20);
  }

  Serial.println();
  Serial.println("=============================");
  Serial.println("  INVENTARIO RFID INTELIGENTE");
  Serial.println("=============================");

  // ---------- WiFi ----------
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("Conectando a WiFi");
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 15000) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Pagina web: http://");
    Serial.println(WiFi.localIP());
    if (MDNS.begin("inventario")) {
      Serial.println("Tambien:    http://inventario.local");
    }
  } else {
    Serial.println("Sin WiFi (se seguira intentando). Los LEDs funcionan igual.");
  }

  // ---------- Supabase ----------
  colaEventos = xQueueCreate(20, sizeof(Evento));
  xTaskCreatePinnedToCore(tareaSupabase, "supabase", 12288, NULL, 1, NULL, 0);

  // ---------- Servidor web ----------
  server.on("/", HTTP_GET, [](AsyncWebServerRequest* request) {
    request->send(200, "text/html", INDEX_HTML);
  });

  server.on("/api/estado", HTTP_GET, [](AsyncWebServerRequest* request) {
    request->send(200, "application/json", estadoJSON());
  });

  // La pagina lee el historial directamente de Supabase desde el navegador
  server.on("/api/config", HTTP_GET, [](AsyncWebServerRequest* request) {
    String j = "{\"url\":\"" + String(SUPABASE_URL) +
               "\",\"key\":\"" + String(SUPABASE_KEY) +
               "\",\"tabla\":\"" + String(SUPABASE_TABLA) + "\"}";
    request->send(200, "application/json", j);
  });

  server.addHandler(&eventos);
  server.begin();

  Serial.println("Esperando objetos...");
}


// =====================================================
// LOOP
// =====================================================

void loop() {

  // 1) Consultar los 3 lectores
  for (int i = 0; i < NUM_LECTORES; i++) {
    leerLector(i);
  }

  unsigned long ahora = millis();
  bool arrancando = ahora < TIEMPO_ARRANQUE;   // inventario inicial: no genera eventos
  bool huboCambio = false;

  // 2) Que hay en cada lector
  for (int i = 0; i < NUM_LECTORES; i++) {
    bool activo = estadoLector[i].visto && (ahora - estadoLector[i].ultimaVez <= TIMEOUT);
    int nuevo = activo ? estadoLector[i].ultimoLeido : VACIO;

    if (nuevo != estadoLector[i].contenido) {
      estadoLector[i].contenido = nuevo;
      huboCambio = true;

      if (nuevo == DESCONOCIDO) {
        Serial.printf("Lector %d: TAG NO RECONOCIDO, UID %s\n", i + 1, estadoLector[i].uidTexto);
      }
    }
  }

  // 3) Estado de cada objeto (retirado / devuelto)
  for (int i = 0; i < NUM_OBJETOS; i++) {
    bool presente = objetos[i].visto && (ahora - objetos[i].ultimaVez <= TIMEOUT);

    if (presente != objetos[i].presente) {
      objetos[i].presente = presente;
      huboCambio = true;

      if (!arrancando) {
        registrarEvento(i, presente ? "DEVUELTO" : "RETIRADO");
      }
    }
  }

  // 4) LEDs y aviso a la pagina web
  actualizarLEDs();

  if (huboCambio) {
    eventos.send(estadoJSON().c_str(), "estado", millis());
  }

  delay(30);
}
