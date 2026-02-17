/*
 * GreenRoute Mesh — ESP32 Firmware
 *
 * Sensors: BME680 (temp/hum/pressure/gas), MQ135 (CO₂), MQ7 (CO),
 *          Dust (optical), GPS (NEO-6M), OLED (SH1106)
 *
 * Sends JSON to backend /api/ingest every 3 seconds via WiFi.
 * Update serverURL with your ngrok tunnel address.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_BME680.h>
#include <TinyGPSPlus.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>

// ================= WIFI =================
const char* ssid = "ESP32";
const char* password = "12345678";

// ================= SERVER =================
// *** UPDATE THIS with your ngrok URL (run: python start.py) ***
const char* serverURL = "https://YOUR-NGROK-URL.ngrok-free.dev/api/ingest";

// Device identity — backend tracks this node by this ID
const char* deviceId = "esp32-vanguard-001";

// Send interval (milliseconds) — 3 seconds between uploads
#define SEND_INTERVAL 3000

// ================= OLED (SH1106) =================
Adafruit_SH1106G display = Adafruit_SH1106G(128, 64, &Wire, -1);

// ================= SENSORS =================
Adafruit_BME680 bme;
TinyGPSPlus gps;
HardwareSerial gpsSerial(2);

#define DUST_PIN 34
#define MQ135_PIN 35
#define MQ7_PIN 32

unsigned long lastSend = 0;
unsigned long lastScreenChange = 0;
int screen = 0;
int sendCount = 0;
bool lastSendOk = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // ---- WiFi ----
  Serial.print("Connecting WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("Backend: ");
  Serial.println(serverURL);

  // ---- I2C ----
  Wire.begin(21, 22);

  // ---- OLED ----
  if (!display.begin(0x3C, true)) {
    Serial.println("OLED not found");
    while (1);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(10, 10);
  display.println("GreenRoute Node");
  display.setCursor(10, 25);
  display.println(deviceId);
  display.setCursor(10, 45);
  display.println("Connecting...");
  display.display();
  delay(2000);

  // ---- BME680 ----
  if (!bme.begin(0x76)) {
    bme.begin(0x77);
  }
  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setGasHeater(320, 150);

  // ---- GPS ----
  gpsSerial.begin(9600, SERIAL_8N1, 16, 17);
}

void loop() {
  int dust = analogRead(DUST_PIN);
  int mq135 = analogRead(MQ135_PIN);
  int mq7 = analogRead(MQ7_PIN);

  float temperature = 0, humidity = 0, pressure = 0, gas = 0;
  if (bme.performReading()) {
    temperature = bme.temperature;
    humidity = bme.humidity;
    pressure = bme.pressure / 100.0;
    gas = bme.gas_resistance / 1000.0;
  }

  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }

  float lat = 0, lon = 0;
  if (gps.location.isValid()) {
    lat = gps.location.lat();
    lon = gps.location.lng();
  }

  // ===== SERIAL PLOTTER =====
  Serial.print(dust); Serial.print(" ");
  Serial.print(mq135); Serial.print(" ");
  Serial.print(mq7); Serial.print(" ");
  Serial.print(temperature); Serial.print(" ");
  Serial.print(humidity); Serial.print(" ");
  Serial.print(pressure); Serial.print(" ");
  Serial.println(gas);

  // ===== OLED UPDATE EVERY 3 SECONDS =====
  if (millis() - lastScreenChange > 3000) {
    updateOLED(dust, mq135, mq7, temperature, humidity, pressure, gas, lat, lon);
    lastScreenChange = millis();
  }

  // ===== SEND TO BACKEND =====
  if (WiFi.status() == WL_CONNECTED && millis() - lastSend > SEND_INTERVAL) {
    String jsonData = "{";
    jsonData += "\"device_id\":\"" + String(deviceId) + "\",";
    jsonData += "\"dust\":" + String(dust) + ",";
    jsonData += "\"mq135\":" + String(mq135) + ",";
    jsonData += "\"mq7\":" + String(mq7) + ",";
    jsonData += "\"temperature\":" + String(temperature, 2) + ",";
    jsonData += "\"humidity\":" + String(humidity, 2) + ",";
    jsonData += "\"pressure\":" + String(pressure, 2) + ",";
    jsonData += "\"gas\":" + String(gas, 2) + ",";
    jsonData += "\"latitude\":" + String(lat, 6) + ",";
    jsonData += "\"longitude\":" + String(lon, 6);
    jsonData += "}";

    HTTPClient http;
    http.begin(serverURL);
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(jsonData);

    sendCount++;
    lastSendOk = (httpCode == 201);

    if (httpCode == 201) {
      Serial.println("[OK] Data sent to backend");
    } else {
      Serial.print("[ERR] HTTP ");
      Serial.println(httpCode);
    }

    http.end();
    lastSend = millis();
  }

  delay(100);
}

// ================= OLED DISPLAY =================
void updateOLED(int dust, int mq135, int mq7,
                float temperature, float humidity,
                float pressure, float gas,
                float lat, float lon) {

  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);

  if (screen == 0) {
    display.println("Dust");
    display.setTextSize(3);
    display.setCursor(0, 20);
    display.println(dust);
  } else if (screen == 1) {
    display.println("MQ135");
    display.setTextSize(3);
    display.setCursor(0, 20);
    display.println(mq135);
  } else if (screen == 2) {
    display.println("MQ7");
    display.setTextSize(3);
    display.setCursor(0, 20);
    display.println(mq7);
  } else if (screen == 3) {
    display.println("Temp (C)");
    display.setTextSize(2);
    display.setCursor(0, 25);
    display.println(temperature, 1);
  } else if (screen == 4) {
    display.println("Humidity (%)");
    display.setTextSize(2);
    display.setCursor(0, 25);
    display.println(humidity, 1);
  } else if (screen == 5) {
    display.println("Pressure (hPa)");
    display.setTextSize(2);
    display.setCursor(0, 25);
    display.println(pressure, 1);
  } else if (screen == 6) {
    display.println("Gas (kOhm)");
    display.setTextSize(2);
    display.setCursor(0, 25);
    display.println(gas, 1);
  } else {
    display.println("GreenRoute");
    display.setTextSize(1);
    display.setCursor(0, 15);
    display.print("Sent: ");
    display.print(sendCount);
    display.print(lastSendOk ? " OK" : " ERR");
    display.setCursor(0, 30);
    display.print("Lat: ");
    display.print(lat, 4);
    display.setCursor(0, 42);
    display.print("Lon: ");
    display.print(lon, 4);
    display.setCursor(0, 54);
    display.print("WiFi: ");
    display.print(WiFi.RSSI());
    display.print("dBm");
  }

  display.display();
  screen++;
  if (screen > 7) screen = 0;
}
