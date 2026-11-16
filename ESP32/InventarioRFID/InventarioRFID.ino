// =====================================================================
//  INVENTARIO RFID -> API THESORA
//
//  Cada lector RC522 vigila una posicion. El ESP32 informa los UID y
//  canales a la API, que valida los activos y sus prestamos.
//  El mapeo RFID/posicion se administra en Thesora y se descarga al
//  conectar y cada 10 s. Una posicion puede contener varios activos.
//
//  Placa: ESP32 Dev Module.
//  Librerias: RFID_MFRC522v2 2.0.6 y ArduinoJson 7.
// =====================================================================

#include <SPI.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <time.h>
#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>

// =====================================
// CONFIGURACION: EDITAR ESTE BLOQUE
// =====================================

const char* WIFI_SSID = "TU_WIFI";          // solo redes de 2.4 GHz
const char* WIFI_PASS = "TU_CLAVE";

const char* API_URL = "https://thesora.redskycol.com/api";
const char* DEVICE_API_KEY = "TU_CLAVE_DEL_DISPOSITIVO";  // emitida por Thesora al registrar el ESP32

// Debe coincidir con el dispositivo registrado en Thesora.
// Solo letras, numeros, guiones y guiones bajos.
const char* DISPOSITIVO_ID = "stand-01";

// CA oficial: https://pki.goog/repo/certs/gtsr4.pem
// Cadena del dominio verificada con GTS Root R4. Actualizar si cambia la CA.
const char API_ROOT_CA[] PROGMEM = R"PEM(
-----BEGIN CERTIFICATE-----
MIICCTCCAY6gAwIBAgINAgPlwGjvYxqccpBQUjAKBggqhkjOPQQDAzBHMQswCQYD
VQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEUMBIG
A1UEAxMLR1RTIFJvb3QgUjQwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAwMDAw
WjBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2Vz
IExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjQwdjAQBgcqhkjOPQIBBgUrgQQAIgNi
AATzdHOnaItgrkO4NcWBMHtLSZ37wWHO5t5GvWvVYRg1rkDdc/eJkTBa6zzuhXyi
QHY7qca4R9gq55KRanPpsXI5nymfopjTX15YhmUPoYRlBtHci8nHc8iMai/lxKvR
HYqjQjBAMA4GA1UdDwEB/wQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQW
BBSATNbrdP9JNqPV2Py1PsVq8JQdjDAKBggqhkjOPQQDAwNpADBmAjEA6ED/g94D
9J+uHXqnLrmvT/aDHQ4thQEd0dlq7A/Cr8deVl5c1RxYIigL9zC2L7F8AjEA8GE8
p/SgguMh1YQdc4acLa/KNJvxn7kjNuK8YAOdgLOaVsjh4rsUecrNIdSUtUlD
-----END CERTIFICATE-----
)PEM";

// =====================================
// LECTORES Y LEDS
// =====================================

// LECTOR 1 - CAJON 1
MFRC522DriverPinSimple ss_pin1(5);
MFRC522DriverSPI driver1{ss_pin1};
MFRC522 lector1{driver1};

// LECTOR 2 - CAJON 2
MFRC522DriverPinSimple ss_pin2(4);
MFRC522DriverSPI driver2{ss_pin2};
MFRC522 lector2{driver2};

// LECTOR 3 - CAJON 3
MFRC522DriverPinSimple ss_pin3(25);
MFRC522DriverSPI driver3{ss_pin3};
MFRC522 lector3{driver3};

// Para agregar un lector: copiar las tres lineas de arriba con otro pin
// y agregarlo a estas dos listas.
MFRC522* const LECTORES[] = { &lector1, &lector2, &lector3 };

// LED indicador de cada lector, en el mismo orden. -1 = ese lector no
// tiene LED.
//   Encendido fijo   -> la app pide senalar ese sitio
//   Parpadeo rapido  -> hay un objeto que no va en ese sitio
const int8_t PIN_LED[] = { 22, 17, 26 };

const uint8_t NUM_LECTORES = sizeof(LECTORES) / sizeof(LECTORES[0]);
static_assert(sizeof(PIN_LED) / sizeof(PIN_LED[0]) == sizeof(LECTORES) / sizeof(LECTORES[0]),
              "PIN_LED necesita un valor por cada lector");

// =====================================
// TIEMPOS
// =====================================

#define FIRMWARE "2.0.0"

const unsigned long TIMEOUT          = 800;    // ms sin leer un tag = fue retirado
const unsigned long TIEMPO_ARRANQUE  = 3000;   // ms iniciales: solo se hace inventario
const unsigned long CADA_CONFIG      = 10000;  // descargar el mapeo
const unsigned long CADA_SENALES     = 2000;   // preguntar que LED encender
const unsigned long CADA_LATIDO      = 30000;  // avisar "sigo vivo"
const unsigned long ESPERA_REINTENTO = 2000;   // tras un envio fallido
const unsigned long ESPERA_WIFI      = 15000;  // entre intentos de reconexion

const uint8_t MAX_TAGS_POR_LECTOR = 4;
const uint8_t MAX_RECURSOS        = 32;
const uint8_t MAX_AVISTAMIENTOS   = 16;
const uint8_t TAM_COLA            = 64;   // eventos que esperan si no hay WiFi
const uint8_t TAM_LOTE            = 8;    // eventos por peticion

// =====================================
// ESTRUCTURAS
// =====================================

// Una fila del mapeo descargado de la API Thesora.
struct Recurso {
  char    uid[21];   // UID en hexadecimal, mayusculas
  char    id[16];    // 'ACT-004'
  uint8_t lector;    // lector asignado; 0 = cualquiera
};

// Un tag que esta ahora mismo sobre un lector.
struct Avistamiento {
  bool          activo;
  char          uid[21];
  uint8_t       lector;
  unsigned long ultimaVez;
};

enum TipoEvento : uint8_t { EV_INICIO, EV_PRESENTE, EV_DEVUELTO, EV_RETIRADO };
const char* const NOMBRE_EVENTO[] = { "INICIO", "PRESENTE", "DEVUELTO", "RETIRADO" };

struct Evento {
  uint32_t   seq;
  uint32_t   ms;       // millis() en el momento del evento
  TipoEvento tipo;
  uint8_t    lector;
  char       uid[21];
};

enum Clase : uint8_t { CL_OK, CL_LUGAR_INCORRECTO, CL_DESCONOCIDO };

// =====================================
// ESTADO
// =====================================

// Mapeo. Lo escribe la tarea de red y lo lee el loop: va con candado.
Recurso           recursos[MAX_RECURSOS];
uint8_t           numRecursos = 0;
volatile bool     configLista = false;
SemaphoreHandle_t candadoConfig;

Avistamiento avistamientos[MAX_AVISTAMIENTOS];

QueueHandle_t colaEventos;
uint32_t      secuencia = 0;
uint32_t      arranque  = 0;        // cuantas veces ha encendido este ESP32

volatile bool     enArranque   = true;
volatile uint32_t mascaraSenal = 0;  // bit 0 = lector 1, bit 1 = lector 2...

Preferences       memoria;
WiFiClientSecure  clienteTLS;
HTTPClient        http;

// =====================================
// UTILIDADES
// =====================================

void uidATexto(const MFRC522Constants::Uid& uid, char* salida) {
  byte n = uid.size > 10 ? 10 : uid.size;
  for (byte i = 0; i < n; i++) {
    sprintf(salida + 2 * i, "%02X", uid.uidByte[i]);
  }
  salida[2 * n] = '\0';
}

// Devuelve true una vez cada "intervalo" ms.
bool toca(unsigned long& ultimaVez, unsigned long intervalo) {
  if (millis() - ultimaVez < intervalo) return false;
  ultimaVez = millis();
  return true;
}

// Busca el UID en el mapeo y dice si ese lector es su sitio.
// Copia el codigo del recurso en "id" (o el UID si es desconocido).
Clase clasificar(const char* uid, uint8_t lector, char* id, size_t tamId) {
  Clase clase = CL_DESCONOCIDO;
  strlcpy(id, uid, tamId);

  xSemaphoreTake(candadoConfig, portMAX_DELAY);
  for (uint8_t i = 0; i < numRecursos; i++) {
    if (strcmp(recursos[i].uid, uid) == 0) {
      strlcpy(id, recursos[i].id, tamId);
      clase = (recursos[i].lector == 0 || recursos[i].lector == lector)
                ? CL_OK
                : CL_LUGAR_INCORRECTO;
      break;
    }
  }
  xSemaphoreGive(candadoConfig);

  return clase;
}

// =====================================
// EVENTOS
// =====================================

void encolarEvento(TipoEvento tipo, const char* uid, uint8_t lector) {
  Evento e = {};
  e.seq    = ++secuencia;
  e.ms     = millis();
  e.tipo   = tipo;
  e.lector = lector;
  if (uid) strlcpy(e.uid, uid, sizeof(e.uid));

  if (xQueueSend(colaEventos, &e, 0) != pdTRUE) {
    Serial.println("[COLA] Llena: se perdio un evento");
  }
}

// =====================================
// REGISTRAR UNA LECTURA
// =====================================

void anotarLectura(const char* uid, uint8_t lector) {
  int libre = -1;

  for (uint8_t i = 0; i < MAX_AVISTAMIENTOS; i++) {
    Avistamiento& a = avistamientos[i];

    if (a.activo && a.lector == lector && strcmp(a.uid, uid) == 0) {
      a.ultimaVez = millis();   // sigue ahi: nada que avisar
      return;
    }
    if (!a.activo && libre < 0) libre = i;
  }

  if (libre < 0) {
    Serial.println("[RFID] Demasiados tags a la vez");
    return;
  }

  // TAG NUEVO EN ESTE LECTOR

  Avistamiento& a = avistamientos[libre];
  a.activo    = true;
  a.lector    = lector;
  a.ultimaVez = millis();
  strlcpy(a.uid, uid, sizeof(a.uid));

  encolarEvento(enArranque ? EV_PRESENTE : EV_DEVUELTO, uid, lector);

  char id[21];
  Clase clase = clasificar(uid, lector, id, sizeof(id));

  if (clase == CL_OK || !configLista) {
    Serial.printf("CAJON %u - %s %s\n", lector, id, enArranque ? "PRESENTE" : "REGRESADO");
    return;
  }

  Serial.println();
  Serial.println("!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
  Serial.printf("ERROR EN CAJON %u\n", lector);
  if (clase == CL_LUGAR_INCORRECTO) {
    Serial.printf("%s NO VA EN ESTE SITIO\n", id);
  } else {
    Serial.printf("TAG DESCONOCIDO: %s\n", uid);
    Serial.println("Para registrarlo: Thesora -> Administracion -> Activos -> UID RFID");
  }
  Serial.println("!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
  Serial.println();
}

// =====================================
// LEER TODOS LOS TAGS DE UN LECTOR
// =====================================

void escanearLector(uint8_t indice) {
  MFRC522& lector = *LECTORES[indice];

  byte bufferATQA[2];
  byte bufferSize = sizeof(bufferATQA);

  // WakeupA despierta a todos los tags, incluidos los ya leidos.
  MFRC522::StatusCode status = lector.PICC_WakeupA(bufferATQA, &bufferSize);

  for (uint8_t n = 0; n < MAX_TAGS_POR_LECTOR; n++) {

    if (
      status != MFRC522Constants::STATUS_OK &&
      status != MFRC522Constants::STATUS_COLLISION
    ) {
      break;
    }

    if (lector.PICC_Select(&(lector.uid)) != MFRC522Constants::STATUS_OK) {
      break;
    }

    char uid[21];
    uidATexto(lector.uid, uid);
    anotarLectura(uid, indice + 1);

    // Se duerme el tag leido y se pregunta si queda otro. RequestA no
    // despierta a los dormidos, asi que solo contestan los que faltan.
    lector.PICC_HaltA();

    bufferSize = sizeof(bufferATQA);
    status = lector.PICC_RequestA(bufferATQA, &bufferSize);
  }
}

// =====================================
// DETECTAR RETIROS
// =====================================

void detectarRetiros() {
  for (uint8_t i = 0; i < MAX_AVISTAMIENTOS; i++) {
    Avistamiento& a = avistamientos[i];

    if (a.activo && millis() - a.ultimaVez > TIMEOUT) {
      a.activo = false;

      encolarEvento(EV_RETIRADO, a.uid, a.lector);

      char id[21];
      Clase clase = clasificar(a.uid, a.lector, id, sizeof(id));

      if (clase == CL_OK || !configLista) {
        Serial.printf("CAJON %u - %s TOMADO\n", a.lector, id);
      } else {
        Serial.printf("CAJON %u - OBJETO NO ASOCIADO RETIRADO\n", a.lector);
        Serial.println("Sitio disponible nuevamente");
      }
    }
  }
}

// =====================================
// LEDS
// =====================================

void actualizarLeds() {
  bool error[NUM_LECTORES] = {};

  if (configLista) {
    for (uint8_t i = 0; i < MAX_AVISTAMIENTOS; i++) {
      const Avistamiento& a = avistamientos[i];
      if (!a.activo) continue;

      char id[21];
      if (clasificar(a.uid, a.lector, id, sizeof(id)) != CL_OK) {
        error[a.lector - 1] = true;
      }
    }
  }

  bool parpadeo = (millis() / 150) % 2;
  uint32_t senal = mascaraSenal;

  for (uint8_t i = 0; i < NUM_LECTORES; i++) {
    if (PIN_LED[i] < 0) continue;

    bool encendido = error[i] ? parpadeo : ((senal >> i) & 1);
    digitalWrite(PIN_LED[i], encendido ? HIGH : LOW);
  }
}

// =====================================
// MAPEO: MEMORIA LOCAL
// =====================================
// La ultima tabla descargada se guarda en la flash, para que el ESP32
// sepa que va en cada sitio aunque encienda sin WiFi.

void cargarConfigGuardada() {
  if (!memoria.begin("inventario", true)) return;

  size_t bytes = memoria.getBytesLength("config");
  if (bytes > 0 && bytes <= sizeof(recursos) && bytes % sizeof(Recurso) == 0) {
    memoria.getBytes("config", recursos, bytes);
    numRecursos = bytes / sizeof(Recurso);
    configLista = true;
  }
  memoria.end();
}

void guardarConfig() {
  if (!memoria.begin("inventario", false)) return;

  if (numRecursos > 0) {
    memoria.putBytes("config", recursos, numRecursos * sizeof(Recurso));
  } else {
    memoria.remove("config");
  }
  memoria.end();
}

// Muestra los activos asignados a cada lector segun Thesora.
void imprimirConfig() {
  Serial.printf("[CONFIG] Mapeo de %s:\n", DISPOSITIVO_ID);

  for (uint8_t lector = 1; lector <= NUM_LECTORES; lector++) {
    Serial.printf("  CAJON %u: ", lector);
    bool alguno = false;
    for (uint8_t i = 0; i < numRecursos; i++) {
      if (recursos[i].lector == lector) {
        Serial.printf("%s%s (tag %s)", alguno ? ", " : "", recursos[i].id, recursos[i].uid);
        alguno = true;
      }
    }
    Serial.println(alguno ? "" : "(sin objeto asignado)");
  }

  for (uint8_t i = 0; i < numRecursos; i++) {
    if (recursos[i].lector == 0) {
      Serial.printf("  CUALQUIER CAJON: %s (tag %s)\n", recursos[i].id, recursos[i].uid);
    } else if (recursos[i].lector > NUM_LECTORES) {
      Serial.printf("  AVISO: %s asignado al cajon %u, que no existe en este stand\n",
                    recursos[i].id, recursos[i].lector);
    }
  }
}

// =====================================
// API THESORA
// =====================================
// Todo lo de esta seccion corre en la tarea de red, nunca en el loop.

String rutaDispositivo(const char* operacion) {
  return String("/dispositivos/") + DISPOSITIVO_ID + "/" + operacion;
}

// Hace una peticion y devuelve el codigo HTTP (negativo = no hubo conexion).
int peticion(const char* metodo, const String& ruta, const char* cuerpo,
             String* respuesta) {
  // TLS necesita una hora valida. SNTP se sincroniza sin frenar los lectores;
  // hasta entonces se conserva la configuracion y el lote para reintentarlos.
  if (time(nullptr) < 1704067200) {
    Serial.println("[API] Esperando sincronizacion de hora para verificar TLS");
    return -1;
  }

  http.setReuse(true);
  http.setConnectTimeout(8000);
  http.setTimeout(8000);

  if (!http.begin(clienteTLS, String(API_URL) + ruta)) return -1;

  http.addHeader("X-Device-Key", DEVICE_API_KEY);
  http.addHeader("Accept", "application/json");
  if (cuerpo) http.addHeader("Content-Type", "application/json");

  int codigo = http.sendRequest(metodo, (uint8_t*)cuerpo, cuerpo ? strlen(cuerpo) : 0);
  if (codigo > 0) {
    String texto = http.getString();
    if (codigo >= 400) {
      Serial.printf("[API] Error HTTP %d en %s\n", codigo, ruta.c_str());
    }
    if (respuesta) *respuesta = texto;
  } else {
    Serial.printf("[API] Sin respuesta (%s)\n", http.errorToString(codigo).c_str());
  }
  http.end();
  if (codigo <= 0) clienteTLS.stop();
  return codigo;
}

// Solo un ACK completo del backend permite sacar este lote de la cola.
bool enviarLote(const Evento* lote, uint8_t cantidad) {
  if (cantidad == 0 || cantidad > TAM_LOTE) return false;

  JsonDocument documento;
  documento["arranque"] = arranque;
  JsonArray eventos = documento["eventos"].to<JsonArray>();
  unsigned long ahora = millis();

  for (uint8_t i = 0; i < cantidad; i++) {
    const Evento& e = lote[i];
    JsonObject evento = eventos.add<JsonObject>();
    evento["secuencia"] = e.seq;
    evento["tipo"] = NOMBRE_EVENTO[e.tipo];
    evento["antiguedad_ms"] = (uint32_t)(ahora - e.ms);
    if (e.tipo == EV_INICIO) {
      evento["uid"] = nullptr;
      evento["canal"] = nullptr;
    } else {
      evento["uid"] = e.uid;
      evento["canal"] = e.lector;
    }
  }

  static char cuerpo[2048];
  if (documento.overflowed() || measureJson(documento) >= sizeof(cuerpo)) {
    Serial.println("[API] No se pudo serializar el lote; se conserva para reintentar");
    return false;
  }
  serializeJson(documento, cuerpo, sizeof(cuerpo));

  String respuesta;
  if (peticion("POST", rutaDispositivo("eventos"), cuerpo, &respuesta) != 202) {
    return false;
  }

  JsonDocument confirmacion;
  if (deserializeJson(confirmacion, respuesta)
      || !confirmacion["aceptados"].is<uint32_t>()
      || !confirmacion["duplicados"].is<uint32_t>()) {
    Serial.println("[API] ACK invalido; se conserva el lote");
    return false;
  }
  uint32_t aceptados = confirmacion["aceptados"];
  uint32_t duplicados = confirmacion["duplicados"];
  if (aceptados > cantidad || duplicados > cantidad || aceptados + duplicados != cantidad) {
    Serial.println("[API] ACK incompleto; se conserva el lote");
    return false;
  }

  Serial.printf("[API] Lote confirmado: %lu nuevo(s), %lu duplicado(s)\n",
                (unsigned long)aceptados, (unsigned long)duplicados);
  return true;
}

// Descarga el mapeo JSON. Una respuesta invalida no sustituye la copia local.
bool descargarConfig() {
  String respuesta;
  if (peticion("GET", rutaDispositivo("configuracion"), nullptr, &respuesta) != 200) {
    return false;
  }
  JsonDocument documento;
  if (deserializeJson(documento, respuesta) || !documento.is<JsonArray>()
      || documento.size() > MAX_RECURSOS) {
    Serial.println("[API] Configuracion invalida o mayor que MAX_RECURSOS; se conserva la anterior");
    return false;
  }

  static Recurso nuevos[MAX_RECURSOS];
  memset(nuevos, 0, sizeof(nuevos));
  uint8_t cantidad = 0;
  for (JsonObjectConst fila : documento.as<JsonArrayConst>()) {
    if (!fila["uid"].is<const char*>() || !fila["codigo"].is<const char*>()
        || !fila["activo_id"].is<uint64_t>() || fila["activo_id"].as<uint64_t>() == 0
        || !fila["canal"].is<uint8_t>()) {
      Serial.println("[API] Fila de configuracion invalida; se conserva la anterior");
      return false;
    }
    String uid = fila["uid"].as<const char*>();
    const char* codigo = fila["codigo"];
    uint8_t canal = fila["canal"];
    bool esHex = uid.length() >= 8 && uid.length() <= 20;
    for (unsigned int i = 0; i < uid.length() && esHex; i++) {
      esHex = isxdigit((unsigned char)uid[i]);
    }
    if (!esHex || !codigo[0] || strlen(codigo) >= sizeof(nuevos[0].id)
        || canal < 1 || canal > NUM_LECTORES) {
      Serial.println("[API] UID, codigo o canal de configuracion invalido; se conserva la anterior");
      return false;
    }
    uid.toUpperCase();
    Recurso& recurso = nuevos[cantidad++];
    strlcpy(recurso.uid, uid.c_str(), sizeof(recurso.uid));
    strlcpy(recurso.id, codigo, sizeof(recurso.id));
    recurso.lector = canal;
  }

  bool cambio = !configLista
                || cantidad != numRecursos
                || memcmp(nuevos, recursos, sizeof(nuevos)) != 0;
  if (cambio) {
    xSemaphoreTake(candadoConfig, portMAX_DELAY);
    memcpy(recursos, nuevos, sizeof(recursos));
    numRecursos = cantidad;
    configLista = true;
    xSemaphoreGive(candadoConfig);
    guardarConfig();
    imprimirConfig();
  }
  return true;
}

// La API devuelve {"canales":[1,2,...]} para este dispositivo autenticado.
bool leerSenales() {
  String respuesta;
  if (peticion("GET", rutaDispositivo("senales"), nullptr, &respuesta) != 200) {
    return false;
  }
  JsonDocument documento;
  if (deserializeJson(documento, respuesta) || !documento["canales"].is<JsonArray>()) {
    return false;
  }

  uint32_t mascara = 0;
  for (JsonVariantConst valor : documento["canales"].as<JsonArrayConst>()) {
    if (!valor.is<uint8_t>()) return false;
    uint8_t canal = valor.as<uint8_t>();
    if (canal < 1 || canal > NUM_LECTORES) return false;
    mascara |= 1UL << (canal - 1);
  }
  mascaraSenal = mascara;
  return true;
}

void enviarLatido() {
  char cuerpo[128];
  snprintf(cuerpo, sizeof(cuerpo),
           "{\"arranque\":%lu,\"firmware\":\"%s\",\"rssi\":%d}",
           (unsigned long)arranque, FIRMWARE, (int)WiFi.RSSI());
  peticion("POST", rutaDispositivo("heartbeat"), cuerpo, nullptr);
}

// =====================================
// TAREA DE RED
// =====================================
// Corre aparte del loop. Asi una peticion lenta o una caida del WiFi
// nunca detiene la lectura de los tags.

void tareaRed(void*) {
  Evento  lote[TAM_LOTE];
  uint8_t enLote = 0;

  bool conectado = false;
  unsigned long ultimoWifi     = millis();
  unsigned long ultimaConfig   = 0;
  unsigned long ultimasSenales = 0;
  unsigned long ultimoLatido   = 0;
  unsigned long ultimoIntento  = 0;
  unsigned long senalesOk      = 0;

  for (;;) {

    // SIN WIFI: esperar y reintentar. Los eventos se quedan en la cola.

    if (WiFi.status() != WL_CONNECTED) {
      if (conectado) {
        conectado = false;
        ultimoWifi = millis();
        Serial.println("[WIFI] Conexion perdida. Los eventos esperan en la cola.");
      }
      if (toca(ultimoWifi, ESPERA_WIFI)) {
        Serial.println("[WIFI] Sin WiFi, reintentando...");
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_PASS);
      }
      mascaraSenal = 0;
      vTaskDelay(pdMS_TO_TICKS(250));
      continue;
    }

    if (!conectado) {
      conectado = true;
      Serial.printf("[WIFI] Conectado. IP: %s\n", WiFi.localIP().toString().c_str());

      // Recien conectado: hacer todo ya, sin esperar los intervalos.
      ultimaConfig   = millis() - CADA_CONFIG;
      ultimasSenales = millis() - CADA_SENALES;
      ultimoLatido   = millis() - CADA_LATIDO;
      ultimoIntento  = millis() - ESPERA_REINTENTO;
    }

    // EVENTOS. Un lote no cambia hasta que la API lo confirma, y solo
    // entonces se saca el siguiente de la cola. Durante el arranque no
    // se envia nada, para que el inventario inicial viaje completo.

    if (!enArranque) {
      if (enLote == 0) {
        while (enLote < TAM_LOTE && xQueueReceive(colaEventos, &lote[enLote], 0) == pdTRUE) {
          enLote++;
        }
        if (enLote > 0) ultimoIntento = millis() - ESPERA_REINTENTO;
      }

      if (enLote > 0 && toca(ultimoIntento, ESPERA_REINTENTO)) {
        if (enviarLote(lote, enLote)) {
          enLote = 0;
        }
      }
    }

    // TAREAS PERIODICAS

    if (toca(ultimaConfig, CADA_CONFIG)) {
      descargarConfig();
    }

    if (toca(ultimasSenales, CADA_SENALES)) {
      if (leerSenales()) {
        senalesOk = millis();
      } else if (millis() - senalesOk > 10000) {
        mascaraSenal = 0;   // sin noticias: no dejar un LED encendido
      }
    }

    if (toca(ultimoLatido, CADA_LATIDO)) {
      enviarLatido();
    }

    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

// =====================================
// SETUP
// =====================================

void setup() {

  Serial.begin(115200);

  for (uint8_t i = 0; i < NUM_LECTORES; i++) {
    if (PIN_LED[i] >= 0) {
      pinMode(PIN_LED[i], OUTPUT);
      digitalWrite(PIN_LED[i], LOW);
    }
  }

  SPI.begin();

  Serial.println();
  Serial.println("================================");
  Serial.println("       INVENTARIO RFID");
  Serial.println("================================");

  // INICIAR LOS LECTORES

  for (uint8_t i = 0; i < NUM_LECTORES; i++) {
    LECTORES[i]->PCD_Init();
    delay(50);

    byte version = (byte)LECTORES[i]->PCD_GetVersion();
    if (version == 0x00 || version == 0xFF) {
      Serial.printf("LECTOR %u: NO RESPONDE (revisar cableado)\n", i + 1);
    } else {
      Serial.printf("LECTOR %u: listo\n", i + 1);
    }
  }

  // CONTADOR DE ENCENDIDOS
  // Junto con el numero de secuencia identifica cada evento, para que un
  // reintento no lo guarde dos veces.

  if (memoria.begin("inventario", false)) {
    arranque = (memoria.getUInt("arranque", 0) + 1) & 0x7FFFFFFF;
    memoria.putUInt("arranque", arranque);
    memoria.end();
  } else {
    arranque = esp_random() & 0x7FFFFFFF;
  }

  candadoConfig = xSemaphoreCreateMutex();
  colaEventos   = xQueueCreate(TAM_COLA, sizeof(Evento));

  cargarConfigGuardada();
  if (configLista) {
    imprimirConfig();
  } else {
    Serial.println("[CONFIG] Aun sin mapeo: se descargara al conectar");
  }

  // El primer evento identifica el arranque. Los PRESENTE siguientes son
  // inventario inicial; no confirman devoluciones de prestamos.
  encolarEvento(EV_INICIO, nullptr, 0);

  // WIFI

  clienteTLS.setCACert(API_ROOT_CA);
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");  // SNTP asincrono para validar TLS

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  xTaskCreatePinnedToCore(tareaRed, "red", 16384, nullptr, 1, nullptr, 0);

  Serial.printf("Stand: %s   Encendido numero %lu\n", DISPOSITIVO_ID, (unsigned long)arranque);
  Serial.println("Haciendo inventario inicial...");
  Serial.println();
}

// =====================================
// LOOP
// =====================================

void loop() {

  if (enArranque && millis() > TIEMPO_ARRANQUE) {
    enArranque = false;
    Serial.println("Inventario inicial listo. Esperando movimientos...");
    Serial.println();
  }

  for (uint8_t i = 0; i < NUM_LECTORES; i++) {
    escanearLector(i);
  }

  detectarRetiros();
  actualizarLeds();

  delay(30);
}
