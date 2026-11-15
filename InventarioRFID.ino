#include <SPI.h>
#include <MFRC522v2.h>
#include <MFRC522DriverSPI.h>
#include <MFRC522DriverPinSimple.h>

// =====================================
// CONFIGURACION DE LOS DOS LECTORES
// =====================================

// LECTOR 1 - CAJON 1
MFRC522DriverPinSimple ss_pin1(5);
MFRC522DriverSPI driver1{ss_pin1};
MFRC522 lector1{driver1};

// LECTOR 2 - CAJON 2
MFRC522DriverPinSimple ss_pin2(4);
MFRC522DriverSPI driver2{ss_pin2};
MFRC522 lector2{driver2};

// =====================================
// UID DE LOS OBJETOS
// =====================================

// CAJON 1 - OBJETO 1
byte UID_OBJETO_1[] = {
  0xAF, 0x91, 0xD0, 0x1C
};

// CAJON 1 - OBJETO 2
byte UID_OBJETO_2[] = {
  0x15, 0xF9, 0xDD, 0x00
};

// CAJON 2 - OBJETO 1
// Se asume que 6F123CE corresponde a
// 06 F1 23 CE (4 bytes).
byte UID_OBJETO_3[] = {
  0x06, 0xF1, 0x23, 0xCE
};

// =====================================
// TIEMPO DE DETECCION
// =====================================

const unsigned long TIMEOUT = 800;

// =====================================
// ESTRUCTURA DE OBJETOS
// =====================================

struct Objeto {

  byte* uid;

  bool presente = false;
  bool detectadoAntes = false;

  unsigned long ultimaDeteccion = 0;

};

// =====================================
// OBJETOS DE CADA CAJON
// =====================================

// CAJON 1
Objeto objetosCajon1[2] = {
  {UID_OBJETO_1},
  {UID_OBJETO_2}
};

// CAJON 2
Objeto objetosCajon2[1] = {
  {UID_OBJETO_3}
};

// CONTROL DE OBJETOS INCORRECTOS

bool incorrectoCajon1 = false;
bool incorrectoCajon2 = false;

unsigned long ultimaDeteccionIncorrecto1 = 0;
unsigned long ultimaDeteccionIncorrecto2 = 0;

// =====================================
// COMPARAR UID
// =====================================

bool compararUID(MFRC522& lector, byte uidEsperado[]) {

  if (lector.uid.size != 4) {
    return false;
  }

  for (byte i = 0; i < 4; i++) {

    if (lector.uid.uidByte[i] != uidEsperado[i]) {
      return false;
    }

  }

  return true;
}

// =====================================
// REGISTRAR OBJETO
// =====================================

void registrarObjeto(
  Objeto& objeto,
  byte numeroObjeto,
  byte numeroCajon
) {

  objeto.ultimaDeteccion = millis();

  if (!objeto.presente) {

    if (objeto.detectadoAntes) {

      Serial.print("CAJON ");
      Serial.print(numeroCajon);
      Serial.print(" - OBJETO ");
      Serial.print(numeroObjeto);
      Serial.println(" REGRESADO");

    } else {

      Serial.print("CAJON ");
      Serial.print(numeroCajon);
      Serial.print(" - OBJETO ");
      Serial.print(numeroObjeto);
      Serial.println(" PRESENTE");

      objeto.detectadoAntes = true;
    }

    objeto.presente = true;
  }
}

// =====================================
// REGISTRAR OBJETO INCORRECTO
// =====================================

void registrarIncorrecto(
  bool& incorrecto,
  unsigned long& ultimaDeteccion,
  byte numeroCajon
) {

  ultimaDeteccion = millis();

  if (!incorrecto) {

    Serial.println();
    Serial.println("!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    Serial.print("ERROR EN CAJON ");
    Serial.println(numeroCajon);
    Serial.println("OBJETO NO ASOCIADO");
    Serial.println("ESTE OBJETO NO VA EN ESTE SITIO");
    Serial.println("!!!!!!!!!!!!!!!!!!!!!!!!!!!!");
    Serial.println();

    incorrecto = true;
  }
}

// =====================================
// PROCESAR LECTOR RFID
// =====================================

void procesarLector(
  MFRC522& lector,
  Objeto objetos[],
  byte cantidadObjetos,
  byte numeroCajon,
  bool& incorrecto,
  unsigned long& ultimaDeteccionIncorrecto
) {

  byte bufferATQA[2];
  byte bufferSize = sizeof(bufferATQA);

  MFRC522::StatusCode status =
    lector.PICC_WakeupA(bufferATQA, &bufferSize);

  // DETECTAR TARJETA

  if (
    status == MFRC522Constants::STATUS_OK ||
    status == MFRC522Constants::STATUS_COLLISION
  ) {

    status = lector.PICC_Select(&(lector.uid));

    if (status == MFRC522Constants::STATUS_OK) {

      bool objetoReconocido = false;

      // COMPROBAR OBJETOS ASOCIADOS AL CAJON

      for (byte i = 0; i < cantidadObjetos; i++) {

        if (compararUID(lector, objetos[i].uid)) {

          registrarObjeto(
            objetos[i],
            i + 1,
            numeroCajon
          );

          objetoReconocido = true;
          break;
        }
      }

      // OBJETO NO ASOCIADO

      if (!objetoReconocido) {

        registrarIncorrecto(
          incorrecto,
          ultimaDeteccionIncorrecto,
          numeroCajon
        );

      }

      lector.PICC_HaltA();
    }
  }

  // DETECTAR RETIRO DE OBJETOS

  for (byte i = 0; i < cantidadObjetos; i++) {

    if (
      objetos[i].presente &&
      millis() - objetos[i].ultimaDeteccion > TIMEOUT
    ) {

      objetos[i].presente = false;

      Serial.print("CAJON ");
      Serial.print(numeroCajon);
      Serial.print(" - OBJETO ");
      Serial.print(i + 1);
      Serial.println(" TOMADO");
    }
  }

  // DETECTAR RETIRO DE OBJETO INCORRECTO

  if (
    incorrecto &&
    millis() - ultimaDeteccionIncorrecto > TIMEOUT
  ) {

    incorrecto = false;

    Serial.print("CAJON ");
    Serial.print(numeroCajon);
    Serial.println(" - OBJETO NO ASOCIADO RETIRADO");

    Serial.println("Sitio disponible nuevamente");
    Serial.println();
  }
}

// =====================================
// SETUP
// =====================================

void setup() {

  Serial.begin(115200);

  SPI.begin();

  // INICIAR LOS DOS LECTORES

  lector1.PCD_Init();
  delay(50);

  lector2.PCD_Init();
  delay(50);

  Serial.println();
  Serial.println("================================");
  Serial.println("       INVENTARIO RFID");
  Serial.println("================================");

  Serial.println("LECTOR 1: CAJON 1");
  Serial.println("  - Objeto 1");
  Serial.println("  - Objeto 2");

  Serial.println();

  Serial.println("LECTOR 2: CAJON 2");
  Serial.println("  - Objeto 1");

  Serial.println();
  Serial.println("Sistema iniciado correctamente");
  Serial.println("Esperando objetos...");
  Serial.println();
}

// =====================================
// LOOP
// =====================================

void loop() {

  // LECTOR 1 - CAJON 1

  procesarLector(
    lector1,
    objetosCajon1,
    2,
    1,
    incorrectoCajon1,
    ultimaDeteccionIncorrecto1
  );

  // LECTOR 2 - CAJON 2

  procesarLector(
    lector2,
    objetosCajon2,
    1,
    2,
    incorrectoCajon2,
    ultimaDeteccionIncorrecto2
  );

  delay(100);
}
