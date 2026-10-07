#include <WiFi.h>



#include <WebServer.h>



#include <Update.h>





// ============================================================



// ESP32 EDGEHUB



// Phase 8.5 - ADC / Analog Reading



// ============================================================





// ============================================================



// WIFI CONFIGURATION



// ============================================================



const char* WIFI_SSID = "YOUR_WIFI_SSID";

const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";





// ============================================================



// FIRMWARE VERSION



// ============================================================



#define FIRMWARE_VERSION "1.4.5"





// ============================================================



// WEB SERVER



// ============================================================



WebServer server(80);





// ============================================================



// EXISTING GPIO 2 CONTROL



// ============================================================



const int CONTROL_PIN = 2;





// ============================================================



// PHASE 8.3 - SAFE DIGITAL GPIO REGISTRY



// ============================================================



// Conservative digital GPIO allow-list.

//

// Allowed:

// GPIO 2

// GPIO 4

// GPIO 16

// GPIO 17

// GPIO 18

// GPIO 19

// GPIO 21

// GPIO 22

// GPIO 23

// GPIO 25

// GPIO 26

// GPIO 27

// GPIO 32

// GPIO 33

//

// Excluded:

// GPIO 0       -> boot/strapping

// GPIO 1,3     -> UART0 / serial

// GPIO 5       -> strapping

// GPIO 6-11    -> SPI flash

// GPIO 12      -> strapping

// GPIO 15      -> strapping

// GPIO 34-39   -> input-only



// ============================================================



const int SAFE_GPIO_PINS[] = {



  2,



  4,



  16,



  17,



  18,



  19,



  21,



  22,



  23,



  25,



  26,



  27,



  32,



  33



};





const size_t SAFE_GPIO_COUNT =



  sizeof(SAFE_GPIO_PINS) / sizeof(SAFE_GPIO_PINS[0]);





// ============================================================

// PHASE 8.5 - SAFE ADC1 REGISTRY

// ============================================================



// Phase 8.7 unified digital state registry.
const int SAFE_DIGITAL_PINS[] = {
  2, 4, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33
};

const size_t SAFE_DIGITAL_COUNT =
  sizeof(SAFE_DIGITAL_PINS) / sizeof(SAFE_DIGITAL_PINS[0]);

const int SAFE_ADC_PINS[] = {



  32,



  33,



  34,



  35,



  36,



  39



};





const size_t SAFE_ADC_COUNT =



  sizeof(SAFE_ADC_PINS) / sizeof(SAFE_ADC_PINS[0]);






// ============================================================
// PHASE 8.6 - SAFE PWM REGISTRY
// ============================================================

const int SAFE_PWM_PINS[] = {
  4, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27
};

const size_t SAFE_PWM_COUNT =
  sizeof(SAFE_PWM_PINS) / sizeof(SAFE_PWM_PINS[0]);

const uint32_t PWM_FREQUENCY_HZ = 5000;
const uint8_t PWM_RESOLUTION_BITS = 8;

bool PWM_ACTIVE[SAFE_PWM_COUNT] = {false};
uint8_t PWM_DUTY[SAFE_PWM_COUNT] = {0};

// Phase 8.7: remember the latest ADC sample without performing
// a new ADC conversion from the unified state endpoint.
uint16_t ADC_LAST_RAW[SAFE_ADC_COUNT] = {0};
uint32_t ADC_LAST_MV[SAFE_ADC_COUNT] = {0};
bool ADC_HAS_LAST_READ[SAFE_ADC_COUNT] = {false};
bool ADC_ACTIVE_MODE[SAFE_ADC_COUNT] = {false};

int getADCIndex(int pin) {
  for (size_t i = 0; i < SAFE_ADC_COUNT; i++) {
    if (SAFE_ADC_PINS[i] == pin) {
      return (int)i;
    }
  }
  return -1;
}

bool isSafePWMPin(int pin) {
  for (size_t i = 0; i < SAFE_PWM_COUNT; i++) {
    if (SAFE_PWM_PINS[i] == pin) {
      return true;
    }
  }
  return false;
}

int getPWMChannel(int pin) {
  for (size_t i = 0; i < SAFE_PWM_COUNT; i++) {
    if (SAFE_PWM_PINS[i] == pin) {
      return (int)i;
    }
  }
  return -1;
}


bool isSafeADCPin(int pin) {



  for (size_t i = 0; i < SAFE_ADC_COUNT; i++) {



    if (SAFE_ADC_PINS[i] == pin) {



      return true;



    }



  }



  return false;



}





// ============================================================



// CHECK WHETHER GPIO IS SAFE



// ============================================================



bool isSafeGPIO(int pin) {



  for (size_t i = 0; i < SAFE_GPIO_COUNT; i++) {



    if (SAFE_GPIO_PINS[i] == pin) {



      return true;



    }



  }



  return false;



}





// ============================================================



// ROOT PAGE



// ============================================================



void handleRoot() {



  String message;



  message += "ESP32 EdgeHub is online!\n";



  message += "Firmware: ";



  message += FIRMWARE_VERSION;



  message += "\n";



  message += "IP: ";



  message += WiFi.localIP().toString();



  message += "\n";



  message += "RSSI: ";



  message += String(WiFi.RSSI());



  message += " dBm\n";



  message += "Free Heap: ";



  message += String(ESP.getFreeHeap());



  message += " bytes\n";



  message += "\n";



  message += "Available endpoints:\n";



  message += "/status\n";



  message += "/hardware\n";



  // Existing GPIO 2 compatibility



  message += "/gpio/2/on\n";



  message += "/gpio/2/off\n";



  // Phase 8.3



  message += "/gpio/read?pin=<GPIO>\n";



  message += "/gpio/write?pin=<GPIO>&state=on|off\n";



  // Phase 8.5



  message += "/adc/read?pin=<GPIO>\n";

  message += "/pwm/write?pin=<GPIO>&duty=<0-255>\n";



  // OTA



  message += "/update\n";



  server.send(



    200,



    "text/plain",



    message



  );



}





// ============================================================



// STATUS API



// ============================================================



void handleStatus() {



  String json = "{";



  json += "\"device\":\"ESP32 EdgeHub\",";



  json += "\"status\":\"online\",";



  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";



  json += "\"ssid\":\"" + String(WIFI_SSID) + "\",";



  json += "\"uptime\":" + String(millis() / 1000) + ",";



  json += "\"rssi\":" + String(WiFi.RSSI()) + ",";



  json += "\"gpio2\":" + String(digitalRead(CONTROL_PIN)) + ",";



  json += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";



  json += "\"firmware\":\"" + String(FIRMWARE_VERSION) + "\"";



  json += "}";



  server.send(



    200,



    "application/json",



    json



  );



}





// ============================================================



// PHASE 8.2 / 8.3 / 8.5



// HARDWARE CAPABILITY REGISTRY



// ============================================================



void handleHardware() {



  String json = "{";



  json += "\"device\":\"ESP32 EdgeHub\",";



  json += "\"board\":\"ESP32 Dev Module\",";



  // General digital output candidates



  json += "\"gpio_output\":[";



  json += "2,4,5,13,14,16,17,18,19,21,22,23,25,26,27,32,33";



  json += "],";



  // Input-only GPIOs



  json += "\"gpio_input_only\":[";



  json += "34,35,36,39";



  json += "],";



  // ADC-capable GPIOs



  json += "\"adc\":[";



  json += "32,33,34,35,36,39";



  json += "],";



  // DAC-capable GPIOs



  json += "\"dac\":[";



  json += "25,26";



  json += "],";



  // PWM-capable GPIO candidates



  json += "\"pwm\":[";



  json += "2,4,5,13,14,16,17,18,19,21,22,23,25,26,27,32,33";



  json += "],";



  // Phase 8.3 safe digital GPIO registry



  json += "\"digital_gpio\":[";



  json += "2,4,16,17,18,19,21,22,23,25,26,27,32,33";



  json += "],";



  // GPIOs currently available to AI digital control



  json += "\"ai_controlled_gpio\":[";



  json += "2,4,16,17,18,19,21,22,23,25,26,27,32,33";



  json += "],";



  // Phase 8.5 ADC1 registry



  json += "\"adc1\":[";



  json += "32,33,34,35,36,39";



  json += "],";



  // ADC pins currently available to AI analog control



  json += "\"ai_adc_controlled\":[";



  json += "32,33,34,35,36,39";



  json += "],";



  json += "\"pwm_ai\":[";

  json += "4,16,17,18,19,21,22,23,25,26,27";

  json += "],";

  json += "\"pwm_frequency_hz\":";

  json += String(PWM_FREQUENCY_HZ);

  json += ",";

  json += "\"pwm_resolution_bits\":";

  json += String(PWM_RESOLUTION_BITS);

  json += ",";

  json += "\"ai_pwm_controlled\":[";

  json += "4,16,17,18,19,21,22,23,25,26,27";

  json += "],";

  json += "\"phase\":\"8.7\"";



  json += "}";



  server.send(



    200,



    "application/json",



    json



  );



}





// ============================================================



// EXISTING GPIO 2 ON



// ============================================================



void handleGPIOOn() {



  digitalWrite(



    CONTROL_PIN,



    HIGH



  );



  Serial.println("GPIO 2 -> ON");



  server.send(



    200,



    "application/json",



    "{\"gpio\":2,\"state\":\"ON\"}"



  );



}





// ============================================================



// EXISTING GPIO 2 OFF



// ============================================================



void handleGPIOOff() {



  digitalWrite(



    CONTROL_PIN,



    LOW



  );



  Serial.println("GPIO 2 -> OFF");



  server.send(



    200,



    "application/json",



    "{\"gpio\":2,\"state\":\"OFF\"}"



  );



}





// ============================================================



// PHASE 8.3



// DIGITAL GPIO WRITE



// ============================================================



void handleGPIOWrite(int pin, bool state) {



  // ----------------------------------------------------------



  // SAFETY VALIDATION



  // ----------------------------------------------------------



  if (!isSafeGPIO(pin)) {



    String json = "{";



    json += "\"success\":false,";



    json += "\"gpio\":";



    json += String(pin);



    json += ",";



    json += "\"error\":\"GPIO is not in the safe digital GPIO registry.\"";



    json += "}";



    server.send(



      400,



      "application/json",



      json



    );



    return;



  }



  // ----------------------------------------------------------



  // CONFIGURE GPIO AS OUTPUT



  // ----------------------------------------------------------



  // Detach PWM before switching the pin back to digital output.

  int pwmChannel = getPWMChannel(pin);

  if (pwmChannel >= 0 && PWM_ACTIVE[pwmChannel]) {

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3

    ledcDetach(pin);

#else

    ledcDetachPin(pin);

#endif

    PWM_ACTIVE[pwmChannel] = false;
    PWM_DUTY[pwmChannel] = 0;
  }

  int digitalAdcIndex = getADCIndex(pin);
  if (digitalAdcIndex >= 0) {
    ADC_ACTIVE_MODE[digitalAdcIndex] = false;
  }

  pinMode(



    pin,



    OUTPUT



  );



  // ----------------------------------------------------------



  // WRITE GPIO



  // ----------------------------------------------------------



  digitalWrite(



    pin,



    state ? HIGH : LOW



  );



  // ----------------------------------------------------------



  // READ BACK VALUE



  // ----------------------------------------------------------



  int actualValue = digitalRead(pin);



  // ----------------------------------------------------------



  // SERIAL LOG



  // ----------------------------------------------------------



  Serial.print("GPIO ");



  Serial.print(pin);



  Serial.print(" -> ");



  if (state) {



    Serial.println("ON");



  }



  else {



    Serial.println("OFF");



  }



  // ----------------------------------------------------------



  // JSON RESPONSE



  // ----------------------------------------------------------



  String json = "{";



  json += "\"success\":true,";



  json += "\"gpio\":";



  json += String(pin);



  json += ",";



  json += "\"state\":\"";



  if (state) {



    json += "ON";



  }



  else {



    json += "OFF";



  }



  json += "\",";



  json += "\"value\":";



  json += String(actualValue);



  json += "}";



  server.send(



    200,



    "application/json",



    json



  );



}





// ============================================================



// PHASE 8.3



// DIGITAL GPIO READ



// ============================================================



void handleGPIORead(int pin) {



  // ----------------------------------------------------------



  // SAFETY VALIDATION



  // ----------------------------------------------------------



  if (!isSafeGPIO(pin)) {



    String json = "{";



    json += "\"success\":false,";



    json += "\"gpio\":";



    json += String(pin);



    json += ",";



    json += "\"error\":\"GPIO is not in the safe digital GPIO registry.\"";



    json += "}";



    server.send(



      400,



      "application/json",



      json



    );



    return;



  }



  // ----------------------------------------------------------



  // IMPORTANT:

  // Do not automatically change the pin to INPUT here.

  //

  // This allows us to read back the current state of an output

  // GPIO without accidentally disabling an active output such

  // as GPIO 2.

  // ----------------------------------------------------------



  int value = digitalRead(pin);



  // ----------------------------------------------------------



  // SERIAL LOG



  // ----------------------------------------------------------



  Serial.print("GPIO ");



  Serial.print(pin);



  Serial.print(" read -> ");



  if (value == HIGH) {



    Serial.println("HIGH");



  }



  else {



    Serial.println("LOW");



  }



  // ----------------------------------------------------------



  // JSON RESPONSE



  // ----------------------------------------------------------



  String json = "{";



  json += "\"success\":true,";



  json += "\"gpio\":";



  json += String(pin);



  json += ",";



  json += "\"value\":";



  json += String(value);



  json += ",";



  json += "\"state\":\"";



  if (value == HIGH) {



    json += "HIGH";



  }



  else {



    json += "LOW";



  }



  json += "\"";



  json += "}";



  server.send(



    200,



    "application/json",



    json



  );



}





// ============================================================



// PHASE 8.3



// GPIO READ ROUTE



// ============================================================



void handleGPIOReadRoute() {



  if (!server.hasArg("pin")) {



    server.send(



      400,



      "application/json",



      "{\"success\":false,\"error\":\"Missing pin parameter.\"}"



    );



    return;



  }



  int pin = server.arg("pin").toInt();



  handleGPIORead(pin);



}





// ============================================================



// PHASE 8.3



// GPIO WRITE ROUTE



// ============================================================



void handleGPIOWriteRoute() {



  if (!server.hasArg("pin")) {



    server.send(



      400,



      "application/json",



      "{\"success\":false,\"error\":\"Missing pin parameter.\"}"



    );



    return;



  }



  if (!server.hasArg("state")) {



    server.send(



      400,



      "application/json",



      "{\"success\":false,\"error\":\"Missing state parameter.\"}"



    );



    return;



  }



  int pin = server.arg("pin").toInt();



  String state = server.arg("state");



  state.toLowerCase();



  state.trim();



  if (



    state != "on" &&



    state != "off"



  ) {



    server.send(



      400,



      "application/json",



      "{\"success\":false,\"error\":\"State must be on or off.\"}"



    );



    return;



  }



  handleGPIOWrite(



    pin,



    state == "on"



  );



}





// ============================================================

// PHASE 8.5

// ADC READ HANDLER

// ============================================================



// ============================================================
// PHASE 8.6 - PWM WRITE
// ============================================================

void handlePWMWrite(int pin, int duty) {

  if (!isSafePWMPin(pin)) {
    String json = "{";
    json += "\"success\":false,";
    json += "\"gpio\":";
    json += String(pin);
    json += ",";
    json += "\"error\":\"GPIO is not in the safe PWM registry.\"";
    json += "}";

    server.send(400, "application/json", json);
    return;
  }

  if (duty < 0 || duty > 255) {
    String json = "{";
    json += "\"success\":false,";
    json += "\"gpio\":";
    json += String(pin);
    json += ",";
    json += "\"duty\":";
    json += String(duty);
    json += ",";
    json += "\"error\":\"PWM duty must be between 0 and 255.\"";
    json += "}";

    server.send(400, "application/json", json);
    return;
  }

  int channel = getPWMChannel(pin);

  if (channel < 0) {
    server.send(
      500,
      "application/json",
      "{\"success\":false,\"error\":\"PWM channel mapping failed.\"}"
    );
    return;
  }

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3

  if (!PWM_ACTIVE[channel]) {
    if (!ledcAttach(
      pin,
      PWM_FREQUENCY_HZ,
      PWM_RESOLUTION_BITS
    )) {
      server.send(
        500,
        "application/json",
        "{\"success\":false,\"error\":\"Failed to attach PWM to GPIO.\"}"
      );
      return;
    }
    PWM_ACTIVE[channel] = true;
  }

  ledcWrite(pin, duty);

#else

  if (!PWM_ACTIVE[channel]) {
    ledcSetup(
      channel,
      PWM_FREQUENCY_HZ,
      PWM_RESOLUTION_BITS
    );

    ledcAttachPin(pin, channel);
    PWM_ACTIVE[channel] = true;
  }

  ledcWrite(channel, duty);

#endif

  PWM_DUTY[channel] = (uint8_t)duty;

  Serial.print("PWM GPIO ");
  Serial.print(pin);
  Serial.print(" -> duty ");
  Serial.print(duty);
  Serial.print("/255 (");
  Serial.print((duty * 100) / 255);
  Serial.println("%)");

  String json = "{";
  json += "\"success\":true,";
  json += "\"gpio\":";
  json += String(pin);
  json += ",";
  json += "\"duty\":";
  json += String(duty);
  json += ",";
  json += "\"duty_percent\":";
  json += String((duty * 100.0) / 255.0, 1);
  json += ",";
  json += "\"frequency_hz\":";
  json += String(PWM_FREQUENCY_HZ);
  json += ",";
  json += "\"resolution_bits\":";
  json += String(PWM_RESOLUTION_BITS);
  json += "}";

  server.send(200, "application/json", json);
}


// ============================================================
// PHASE 8.6 - PWM WRITE ROUTE
// ============================================================

void handlePWMWriteRoute() {

  if (!server.hasArg("pin")) {
    server.send(
      400,
      "application/json",
      "{\"success\":false,\"error\":\"Missing pin parameter.\"}"
    );
    return;
  }

  if (!server.hasArg("duty")) {
    server.send(
      400,
      "application/json",
      "{\"success\":false,\"error\":\"Missing duty parameter.\"}"
    );
    return;
  }

  String pinArg = server.arg("pin");
  String dutyArg = server.arg("duty");

  pinArg.trim();
  dutyArg.trim();

  if (pinArg.length() == 0 || dutyArg.length() == 0) {
    server.send(
      400,
      "application/json",
      "{\"success\":false,\"error\":\"Pin and duty must not be empty.\"}"
    );
    return;
  }

  for (size_t i = 0; i < pinArg.length(); i++) {
    if (!isDigit(pinArg[i]) &&
        !(i == 0 && pinArg[i] == '-')) {
      server.send(
        400,
        "application/json",
        "{\"success\":false,\"error\":\"Pin must be an integer.\"}"
      );
      return;
    }
  }

  for (size_t i = 0; i < dutyArg.length(); i++) {
    if (!isDigit(dutyArg[i]) &&
        !(i == 0 && dutyArg[i] == '-')) {
      server.send(
        400,
        "application/json",
        "{\"success\":false,\"error\":\"Duty must be an integer between 0 and 255.\"}"
      );
      return;
    }
  }

  int pin = pinArg.toInt();
  int duty = dutyArg.toInt();

  handlePWMWrite(pin, duty);
}


void handleADCRead(int pin) {



  // ----------------------------------------------------------

  // SAFETY VALIDATION

  // ----------------------------------------------------------



  if (!isSafeADCPin(pin)) {



    String json = "{";



    json += "\"success\":false,";



    json += "\"gpio\":";



    json += String(pin);



    json += ",";



    json += "\"error\":\"GPIO is not in the safe ADC1 registry.\"";



    json += "}";



    server.send(



      400,



      "application/json",



      json



    );



    Serial.print("ADC rejected - GPIO ");



    Serial.println(pin);



    return;



  }



  // ----------------------------------------------------------

  // ADC CONFIGURATION

  // ----------------------------------------------------------



  // ADC1 is used because ADC2 conflicts with Wi-Fi

  // on the classic ESP32.



  // GPIO32/33 are shared-capability pins and are configured

  // as inputs for this analog-read operation.



  pinMode(



    pin,



    INPUT



  );



  analogReadResolution(12);



  analogSetPinAttenuation(



    pin,



    ADC_11db



  );



  // ----------------------------------------------------------

  // ADC READ

  // ----------------------------------------------------------



  uint16_t rawValue =



    analogRead(pin);



  uint32_t milliVolts =



    analogReadMilliVolts(pin);

  int adcIndex = getADCIndex(pin);
  if (adcIndex >= 0) {
    ADC_LAST_RAW[adcIndex] = rawValue;
    ADC_LAST_MV[adcIndex] = milliVolts;
    ADC_HAS_LAST_READ[adcIndex] = true;
    ADC_ACTIVE_MODE[adcIndex] = true;
  }



  // ----------------------------------------------------------

  // SERIAL LOG

  // ----------------------------------------------------------



  Serial.print("ADC GPIO ");



  Serial.print(pin);



  Serial.print(" -> RAW: ");



  Serial.print(rawValue);



  Serial.print(" | mV: ");



  Serial.println(milliVolts);



  // ----------------------------------------------------------

  // JSON RESPONSE

  // ----------------------------------------------------------



  String json = "{";



  json += "\"success\":true,";



  json += "\"gpio\":";



  json += String(pin);



  json += ",";



  json += "\"raw\":";



  json += String(rawValue);



  json += ",";



  json += "\"millivolts\":";



  json += String(milliVolts);



  json += ",";



  json += "\"resolution_bits\":12,";



  json += "\"adc\":\"ADC1\",";



  json += "\"attenuation\":\"11dB\"";



  json += "}";



  server.send(



    200,



    "application/json",



    json



  );



}





// ============================================================

// PHASE 8.5

// ADC READ ROUTE

// ============================================================



// ============================================================
// PHASE 8.7 - UNIFIED HARDWARE STATE
// ============================================================

void handleHardwareState() {

  String json = "{";
  json += "\"success\":true,";
  json += "\"device\":\"ESP32 EdgeHub\",";
  json += "\"firmware\":\"" + String(FIRMWARE_VERSION) + "\",";
  json += "\"phase\":\"8.7\",";
  json += "\"uptime\":" + String(millis() / 1000UL) + ",";

  json += "\"digital_gpio\":[";
  bool firstDigital = true;

  for (size_t i = 0; i < SAFE_DIGITAL_COUNT; i++) {
    int pin = SAFE_DIGITAL_PINS[i];
    int pwmChannel = getPWMChannel(pin);
    int adcIndex = getADCIndex(pin);

    if (!firstDigital) json += ",";
    firstDigital = false;

    json += "{\"gpio\":" + String(pin) + ",";

    if (pwmChannel >= 0 && PWM_ACTIVE[pwmChannel]) {
      json += "\"mode\":\"pwm\",\"state\":null,";
      json += "\"pwm_active\":true,";
      json += "\"duty\":" + String(PWM_DUTY[pwmChannel]);
    } else if (adcIndex >= 0 && ADC_ACTIVE_MODE[adcIndex] && ADC_HAS_LAST_READ[adcIndex]) {
      json += "\"mode\":\"adc_input\",\"state\":null,";
      json += "\"adc_last_raw\":" + String(ADC_LAST_RAW[adcIndex]) + ",";
      json += "\"adc_last_millivolts\":" + String(ADC_LAST_MV[adcIndex]);
    } else {
      json += "\"mode\":\"digital\",\"state\":";
      json += String(digitalRead(pin));
    }

    json += "}";
  }

  json += "],";

  json += "\"pwm\":[";
  for (size_t i = 0; i < SAFE_PWM_COUNT; i++) {
    if (i > 0) json += ",";
    json += "{\"gpio\":" + String(SAFE_PWM_PINS[i]) + ",";
    json += "\"active\":";
    json += PWM_ACTIVE[i] ? "true" : "false";
    json += ",\"duty\":" + String(PWM_DUTY[i]) + ",";
    json += "\"duty_percent\":" + String((PWM_DUTY[i] * 100.0) / 255.0, 1) + ",";
    json += "\"frequency_hz\":" + String(PWM_FREQUENCY_HZ) + ",";
    json += "\"resolution_bits\":" + String(PWM_RESOLUTION_BITS);
    json += "}";
  }
  json += "],";

  json += "\"adc\":[";
  for (size_t i = 0; i < SAFE_ADC_COUNT; i++) {
    if (i > 0) json += ",";
    json += "{\"gpio\":" + String(SAFE_ADC_PINS[i]) + ",";
    json += "\"has_last_read\":";
    json += ADC_HAS_LAST_READ[i] ? "true" : "false";
    if (ADC_HAS_LAST_READ[i]) {
      json += ",\"raw\":" + String(ADC_LAST_RAW[i]) + ",";
      json += "\"millivolts\":" + String(ADC_LAST_MV[i]);
    } else {
      json += ",\"raw\":null,\"millivolts\":null";
    }
    json += ",\"resolution_bits\":12,\"adc\":\"ADC1\",\"attenuation\":\"11dB\"}";
  }
  json += "],";
  json += "\"shared_adc_gpio\":[32,33]";
  json += "}";

  server.send(200, "application/json", json);
}


void handleADCReadRoute() {



  if (!server.hasArg("pin")) {



    server.send(



      400,



      "application/json",



      "{\"success\":false,\"error\":\"Missing pin parameter.\"}"



    );



    return;



  }



  int pin = server.arg("pin").toInt();



  handleADCRead(pin);



}





// ============================================================



// OTA UPDATE PAGE



// ============================================================



void handleUpdatePage() {



  String html;



  html += "<!DOCTYPE html>";



  html += "<html>";



  html += "<head>";



  html += "<meta charset='UTF-8'>";



  html += "<meta name='viewport' ";



  html += "content='width=device-width, initial-scale=1'>";



  html += "<title>ESP32 EdgeHub OTA</title>";



  html += "<style>";



  html += "body{";



  html += "font-family:Arial,sans-serif;";



  html += "background:#f4f6f8;";



  html += "margin:0;";



  html += "padding:40px;";



  html += "}";



  html += ".container{";



  html += "max-width:800px;";



  html += "margin:auto;";



  html += "background:white;";



  html += "padding:40px;";



  html += "border-radius:16px;";



  html += "box-shadow:0 5px 25px rgba(0,0,0,.1);";



  html += "}";



  html += "h1{color:#111827;}";



  html += ".info{";



  html += "background:#eef2ff;";



  html += "padding:20px;";



  html += "border-radius:10px;";



  html += "margin:20px 0;";



  html += "}";



  html += ".upload{";



  html += "border:2px dashed #b8c2d1;";



  html += "padding:35px;";



  html += "text-align:center;";



  html += "border-radius:12px;";



  html += "}";



  html += "button{";



  html += "background:#2563eb;";



  html += "color:white;";



  html += "border:none;";



  html += "padding:14px 28px;";



  html += "font-size:16px;";



  html += "border-radius:8px;";



  html += "cursor:pointer;";



  html += "margin-top:20px;";



  html += "}";



  html += "button:hover{";



  html += "background:#1d4ed8;";



  html += "}";



  html += "input[type=file]{";



  html += "margin-top:20px;";



  html += "}";



  html += ".back{";



  html += "display:inline-block;";



  html += "margin-top:30px;";



  html += "color:#2563eb;";



  html += "text-decoration:none;";



  html += "}";



  html += "</style>";



  html += "</head>";



  html += "<body>";



  html += "<div class='container'>";



  html += "<h1>ESP32 EdgeHub OTA</h1>";



  html += "<div class='info'>";



  html += "<b>Device:</b> ESP32 EdgeHub<br>";



  html += "<b>Firmware:</b> ";



  html += FIRMWARE_VERSION;



  html += "<br>";



  html += "<b>IP:</b> ";



  html += WiFi.localIP().toString();



  html += "<br>";



  html += "<b>Status:</b> ONLINE";



  html += "</div>";



  html += "<div class='upload'>";



  html += "<h2>Upload New Firmware</h2>";



  html += "<p>Select the compiled ESP32 firmware ";



  html += "<b>.bin</b> file.</p>";



  html += "<p>Maximum size: 4 MB</p>";



  html += "<form method='POST' ";



  html += "action='/update' ";



  html += "enctype='multipart/form-data'>";



  html += "<input type='file' ";



  html += "name='firmware' ";



  html += "accept='.bin' ";



  html += "required>";



  html += "<br>";



  html += "<button type='submit'>";



  html += "Upload Firmware";



  html += "</button>";



  html += "</form>";



  html += "</div>";



  html += "<a class='back' href='/'>";



  html += "← Back to ESP32";



  html += "</a>";



  html += "</div>";



  html += "</body>";



  html += "</html>";



  server.send(



    200,



    "text/html",



    html



  );



}





// ============================================================



// OTA UPLOAD HANDLER



// ============================================================



void handleFirmwareUpload() {



  HTTPUpload& upload = server.upload();



  // ----------------------------------------------------------



  // UPLOAD START



  // ----------------------------------------------------------



  if (upload.status == UPLOAD_FILE_START) {



    Serial.println();



    Serial.println("========================================");



    Serial.println("OTA UPDATE STARTED");



    Serial.println("========================================");



    Serial.print("Firmware filename: ");



    Serial.println(upload.filename);



    Serial.println("Preparing flash...");



    if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {



      Serial.println("OTA ERROR: Unable to begin update");



      Update.printError(Serial);



    }



    else {



      Serial.println("OTA flash ready");



    }



  }



  // ----------------------------------------------------------



  // UPLOAD WRITE



  // ----------------------------------------------------------



  else if (upload.status == UPLOAD_FILE_WRITE) {



    if (Update.isRunning()) {



      size_t written = Update.write(



        upload.buf,



        upload.currentSize



      );



      if (written != upload.currentSize) {



        Serial.println("OTA ERROR: Write failed");



        Update.printError(Serial);



      }



      else {



        Serial.print(".");



      }



    }



  }



  // ----------------------------------------------------------



  // UPLOAD END



  // ----------------------------------------------------------



  else if (upload.status == UPLOAD_FILE_END) {



    Serial.println();



    Serial.print("Uploaded firmware size: ");



    Serial.print(upload.totalSize);



    Serial.println(" bytes");



    if (Update.end(true)) {



      Serial.println("========================================");



      Serial.println("OTA UPDATE SUCCESSFUL");



      Serial.println("========================================");



      Serial.println("Firmware written successfully.");



      Serial.println("Restarting ESP32...");



    }



    else {



      Serial.println("========================================");



      Serial.println("OTA UPDATE FAILED");



      Serial.println("========================================");



      Update.printError(Serial);



    }



  }



  // ----------------------------------------------------------



  // UPLOAD ABORTED



  // ----------------------------------------------------------



  else if (upload.status == UPLOAD_FILE_ABORTED) {



    Serial.println();



    Serial.println("OTA UPDATE ABORTED");



    Update.abort();



  }



}





// ============================================================



// OTA UPDATE COMPLETE



// ============================================================



void handleUpdateFinished() {



  if (Update.hasError()) {



    server.send(



      500,



      "application/json",



      "{\"success\":false,\"message\":\"Firmware update failed\"}"



    );



    return;



  }



  server.send(



    200,



    "text/html",



    "<!DOCTYPE html>"



    "<html>"



    "<head>"



    "<meta charset='UTF-8'>"



    "<title>OTA Successful</title>"



    "</head>"



    "<body style='font-family:Arial;text-align:center;"



    "padding:60px;'>"



    "<h1>OTA Update Successful</h1>"



    "<p>ESP32 EdgeHub is restarting...</p>"



    "<p>Please wait a few seconds and refresh the dashboard.</p>"



    "</body>"



    "</html>"



  );



  delay(1000);



  ESP.restart();



}





// ============================================================



// SETUP



// ============================================================



void setup() {



  Serial.begin(115200);



  // ----------------------------------------------------------



  // GPIO 2



  // ----------------------------------------------------------



  pinMode(



    CONTROL_PIN,



    OUTPUT



  );



  digitalWrite(



    CONTROL_PIN,



    LOW



  );



  delay(1000);



  // ----------------------------------------------------------



  // STARTUP MESSAGE



  // ----------------------------------------------------------



  Serial.println();



  Serial.println("========================================");



  Serial.println("          ESP32 EdgeHub");



  Serial.println("========================================");



  Serial.print("Firmware version: ");



  Serial.println(FIRMWARE_VERSION);



  Serial.println();



  // ----------------------------------------------------------



  // WIFI



  // ----------------------------------------------------------



  Serial.println("Connecting to Wi-Fi...");



  WiFi.begin(



    WIFI_SSID,



    WIFI_PASSWORD



  );



  while (WiFi.status() != WL_CONNECTED) {



    delay(500);



    Serial.print(".");



  }



  Serial.println();



  Serial.println("Wi-Fi connected!");



  Serial.print("ESP32 IP Address: ");



  Serial.println(WiFi.localIP());



  Serial.print("Signal strength: ");



  Serial.print(WiFi.RSSI());



  Serial.println(" dBm");



  // ----------------------------------------------------------



  // ROOT ROUTE



  // ----------------------------------------------------------



  server.on(



    "/",



    HTTP_GET,



    handleRoot



  );



  // ----------------------------------------------------------



  // STATUS ROUTE



  // ----------------------------------------------------------



  server.on(



    "/status",



    HTTP_GET,



    handleStatus



  );



  // ----------------------------------------------------------



  // PHASE 8.2 HARDWARE CAPABILITY ROUTE



  // ----------------------------------------------------------



  server.on(



    "/hardware",



    HTTP_GET,



    handleHardware



  );

  // Phase 8.7 unified hardware state
  server.on(
    "/hardware/state",
    HTTP_GET,
    handleHardwareState
  );



  // ----------------------------------------------------------



  // EXISTING GPIO 2 ROUTES



  // ----------------------------------------------------------



  server.on(



    "/gpio/2/on",



    HTTP_GET,



    handleGPIOOn



  );



  server.on(



    "/gpio/2/off",



    HTTP_GET,



    handleGPIOOff



  );



  // ----------------------------------------------------------



  // PHASE 8.3 DIGITAL GPIO READ



  // ----------------------------------------------------------



  server.on(



    "/gpio/read",



    HTTP_GET,



    handleGPIOReadRoute



  );



  // ----------------------------------------------------------



  // PHASE 8.3 DIGITAL GPIO WRITE



  // ----------------------------------------------------------



  server.on(



    "/gpio/write",



    HTTP_GET,



    handleGPIOWriteRoute



  );



  // ----------------------------------------------------------



  // PHASE 8.5 ADC READ



  // ----------------------------------------------------------



  // PHASE 8.6 PWM WRITE

  server.on(

    "/pwm/write",

    HTTP_GET,

    handlePWMWriteRoute

  );



  // PHASE 8.5 ADC READ

  server.on(
    "/adc/read",
    HTTP_GET,
    handleADCReadRoute
  );



  // ----------------------------------------------------------



  // OTA PAGE



  // ----------------------------------------------------------



  server.on(



    "/update",



    HTTP_GET,



    handleUpdatePage



  );



  // ----------------------------------------------------------



  // OTA UPLOAD



  // ----------------------------------------------------------



  server.on(



    "/update",



    HTTP_POST,



    handleUpdateFinished,



    handleFirmwareUpload



  );



  // ----------------------------------------------------------



  // START WEB SERVER



  // ----------------------------------------------------------



  server.begin();



  Serial.println();



  Serial.println("========================================");



  Serial.println("ESP32 EdgeHub web server started!");



  Serial.println();



  Serial.println("Endpoints:");



  Serial.println("/");



  Serial.println("/status");



  Serial.println("/hardware");
  Serial.println("/hardware/state");



  Serial.println("/gpio/2/on");



  Serial.println("/gpio/2/off");



  Serial.println("/gpio/read?pin=<GPIO>");



  Serial.println("/gpio/write?pin=<GPIO>&state=on|off");



  Serial.println("/adc/read?pin=<GPIO>");

  Serial.println("/pwm/write?pin=<GPIO>&duty=<0-255>");



  Serial.println("/update");



  Serial.println();



  Serial.println();

  Serial.println("Phase 8.7 unified hardware state enabled.");
  Serial.println("Phase 8.6 PWM AI control enabled.");

  Serial.println("Safe PWM GPIOs: [4, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27]");

  Serial.println("PWM: 5000 Hz, 8-bit (0-255)");

  Serial.println();

  Serial.print("Firmware: ");



  Serial.println(FIRMWARE_VERSION);



  Serial.println("========================================");



}





// ============================================================



// LOOP



// ============================================================



void loop() {



  server.handleClient();



}
