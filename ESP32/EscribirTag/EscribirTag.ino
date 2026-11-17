// =====================================================================
//  ESCRIBIR TAG RFID
//
//  Herramienta aparte del stand. Usa UN lector RC522 (el del pin 5) para:
//    - mostrar el UID de un tag, para copiarlo en Supabase (recursos.uid_tag)
//    - leer y escribir un texto corto en la memoria del tag
//
//  El inventario identifica los objetos por su UID, que viene de fabrica
//  y no se puede cambiar. Escribir un texto es opcional (por ejemplo, el
//  codigo 'ACT-004' para reconocer el tag a simple vista con un movil).
//
//  Uso: cargar este sketch, abrir el Serial Monitor a 115200 con
//  "Newline" como fin de linea, escribir el texto, pulsar Enter y acercar
//  el tag. Para volver al stand, cargar otra vez InventarioRFID.
//
//  Tags compatibles: MIFARE Classic 1K / 4K / Mini (las tarjetas blancas
//  y llaveros azules que vienen con el RC522) y MIFARE Ultralight / NTAG.
// =====================================================================

#include <SPI.h>
#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>

// Mismo cableado que el lector 1 del stand
MFRC522DriverPinSimple ss_pin(5);
MFRC522DriverSPI driver{ss_pin};
MFRC522 lector{driver};

// Donde se guarda el texto (16 bytes)
//   MIFARE Classic: bloque 4 = primer bloque de datos del sector 1.
//     NUNCA usar los bloques 3, 7, 11...: guardan las claves y escribir
//     en ellos puede dejar el sector inservible.
//   Ultralight / NTAG: paginas 4 a 7, las primeras de usuario.
const byte BLOQUE_CLASSIC = 4;
const byte PAGINA_ULTRALIGHT = 4;
const byte LARGO = 16;

// Clave de fabrica de las tarjetas MIFARE Classic
MFRC522::MIFARE_Key clave = { { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF } };

enum TipoTag { CLASSIC, ULTRALIGHT, NO_SOPORTADO };

char pendiente[LARGO + 1];
bool hayPendiente = false;

// =====================================
// SERIAL: TEXTO A ESCRIBIR
// =====================================

void procesarLinea(char* linea) {
  // Quitar espacios al principio y al final
  while (*linea == ' ') linea++;
  size_t n = strlen(linea);
  while (n > 0 && linea[n - 1] == ' ') linea[--n] = '\0';

  if (n == 0) {
    hayPendiente = false;
    Serial.println("Escritura cancelada. Modo lectura.");
    return;
  }

  if (n > LARGO) {
    Serial.printf("Demasiado largo: %u bytes, maximo %u. (Las tildes ocupan 2.)\n", n, LARGO);
    return;
  }

  strlcpy(pendiente, linea, sizeof(pendiente));
  hayPendiente = true;
  Serial.printf("Acerca el tag para escribir \"%s\"  (Enter vacio = cancelar)\n", pendiente);
}

void leerSerial() {
  static char linea[64];
  static byte n = 0;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;

    if (c == '\n') {
      linea[n] = '\0';
      procesarLinea(linea);
      n = 0;
    } else if (n < sizeof(linea) - 1) {
      linea[n++] = c;
    }
  }
}

// =====================================
// TAG
// =====================================

TipoTag tipoDelTag() {
  MFRC522Constants::PICC_Type tipo = lector.PICC_GetType(lector.uid.sak);

  if (
    tipo == MFRC522Constants::PICC_TYPE_MIFARE_MINI ||
    tipo == MFRC522Constants::PICC_TYPE_MIFARE_1K ||
    tipo == MFRC522Constants::PICC_TYPE_MIFARE_4K
  ) {
    return CLASSIC;
  }
  if (tipo == MFRC522Constants::PICC_TYPE_MIFARE_UL) {
    return ULTRALIGHT;
  }
  return NO_SOPORTADO;
}

bool autenticar() {
  MFRC522::StatusCode s = lector.PCD_Authenticate(
    MFRC522Constants::PICC_CMD_MF_AUTH_KEY_A, BLOQUE_CLASSIC, &clave, &(lector.uid));

  if (s != MFRC522Constants::STATUS_OK) {
    Serial.printf("  No se pudo autenticar (codigo %d). El tag no usa la clave de fabrica.\n", (int)s);
    return false;
  }
  return true;
}

bool leer(TipoTag tipo, byte* datos) {
  byte buffer[18];   // 16 bytes + 2 de CRC
  byte tam = sizeof(buffer);

  if (tipo == CLASSIC && !autenticar()) return false;

  byte direccion = tipo == CLASSIC ? BLOQUE_CLASSIC : PAGINA_ULTRALIGHT;
  MFRC522::StatusCode s = lector.MIFARE_Read(direccion, buffer, &tam);

  if (s != MFRC522Constants::STATUS_OK) {
    Serial.printf("  Error al leer (codigo %d)\n", (int)s);
    return false;
  }

  memcpy(datos, buffer, LARGO);
  return true;
}

bool escribir(TipoTag tipo, const char* texto) {
  byte datos[LARGO] = {};
  memcpy(datos, texto, strlen(texto));   // el resto queda en 0

  MFRC522::StatusCode s;

  if (tipo == CLASSIC) {
    // La autenticacion de leer() sigue valida para el mismo bloque
    s = lector.MIFARE_Write(BLOQUE_CLASSIC, datos, LARGO);
  } else {
    s = MFRC522Constants::STATUS_OK;
    for (byte i = 0; i < 4 && s == MFRC522Constants::STATUS_OK; i++) {
      s = lector.MIFARE_Ultralight_Write(PAGINA_ULTRALIGHT + i, datos + 4 * i, 4);
    }
  }

  if (s != MFRC522Constants::STATUS_OK) {
    Serial.printf("  Error al escribir (codigo %d). El tag puede estar bloqueado.\n", (int)s);
    return false;
  }
  return true;
}

void imprimirContenido(const byte* datos) {
  Serial.print("  Texto: \"");
  for (byte i = 0; i < LARGO && datos[i] != 0; i++) {
    Serial.print(isprint(datos[i]) ? (char)datos[i] : '.');
  }
  Serial.println("\"");

  Serial.print("  Hex:   ");
  for (byte i = 0; i < LARGO; i++) {
    Serial.printf("%02X ", datos[i]);
  }
  Serial.println();
}

void procesarTag() {
  Serial.println();
  Serial.print("UID: ");
  for (byte i = 0; i < lector.uid.size; i++) {
    Serial.printf("%02X", lector.uid.uidByte[i]);
  }
  Serial.println("   <- esto va en recursos.uid_tag");

  TipoTag tipo = tipoDelTag();
  if (tipo == NO_SOPORTADO) {
    Serial.println("  Tipo de tag no soportado para escribir.");
    return;
  }
  Serial.println(tipo == CLASSIC ? "  Tipo: MIFARE Classic" : "  Tipo: MIFARE Ultralight / NTAG");

  byte datos[LARGO];
  if (!leer(tipo, datos)) return;
  Serial.println("  Contenido actual:");
  imprimirContenido(datos);

  if (!hayPendiente) return;

  if (!escribir(tipo, pendiente)) return;

  // Comprobar leyendo de nuevo
  byte verificado[LARGO];
  byte esperado[LARGO] = {};
  memcpy(esperado, pendiente, strlen(pendiente));

  if (leer(tipo, verificado) && memcmp(verificado, esperado, LARGO) == 0) {
    Serial.printf("  ESCRITO Y VERIFICADO: \"%s\"\n", pendiente);
    hayPendiente = false;
    Serial.println("Escribe otro texto o acerca otro tag para leerlo.");
  } else {
    Serial.println("  La verificacion fallo. Vuelve a acercar el tag.");
  }
}

// =====================================
// SETUP Y LOOP
// =====================================

void setup() {
  Serial.begin(115200);

  // Si los lectores 2 y 3 del stand siguen conectados, dejar su SDA en alto
  // para que no respondan a la vez que el lector 1 y no ensucien MISO.
  const byte OTROS_SS[] = { 4, 25 };
  for (byte pin : OTROS_SS) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);
  }

  SPI.begin();
  lector.PCD_Init();
  delay(50);

  Serial.println();
  Serial.println("================================");
  Serial.println("        ESCRIBIR TAG RFID");
  Serial.println("================================");

  byte version = (byte)lector.PCD_GetVersion();
  if (version == 0x00 || version == 0xFF) {
    Serial.println("EL LECTOR NO RESPONDE: revisar cableado");
  }

  Serial.println("Acerca un tag para ver su UID y contenido.");
  Serial.printf("Para escribir: teclea un texto (max %u) y pulsa Enter.\n", LARGO);
  Serial.println("(En el Serial Monitor, fin de linea = \"Newline\")");
}

void loop() {
  leerSerial();

  // Un tag ya procesado queda dormido hasta que se retira y se vuelve a acercar
  if (lector.PICC_IsNewCardPresent() && lector.PICC_ReadCardSerial()) {
    procesarTag();
    lector.PICC_HaltA();
    lector.PCD_StopCrypto1();
  }

  delay(50);
}
