#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ==========================================
// 1. Network & Server Configuration
// ==========================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* SERVER_HOST   = "192.168.1.100";  // Laptop IP running FastAPI Gateway
const int   SERVER_PORT   = 8000;
const char* WS_PATH       = "/ws/robot";

WebSocketsClient webSocket;

// ==========================================
// 2. Hardware Pin Definitions (ESP32-S3 N16R8)
// ==========================================
#define PIN_I2S_MIC_SD    4
#define PIN_I2S_MIC_WS    5
#define PIN_I2S_MIC_SCK   6

#define PIN_I2S_SPK_DIN   7
#define PIN_I2S_SPK_BCLK  15
#define PIN_I2S_SPK_LRC   16

#define PIN_SERVO_PAN     13
#define PIN_SERVO_TILT    14
#define PIN_RELAY         21
#define PIN_BUTTON        10

#define I2C_SDA           8
#define I2C_SCL           9

#define SCREEN_WIDTH      128
#define SCREEN_HEIGHT     64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// ==========================================
// 3. Audio & Buffer Settings
// ==========================================
#define MIC_SAMPLE_RATE   16000
#define SPK_SAMPLE_RATE   24000
#define AUDIO_CHUNK_SAMPLES 480  // 30ms @ 16kHz
uint8_t mic_buffer[AUDIO_CHUNK_SAMPLES * 2]; // 16-bit PCM = 960 bytes

// ==========================================
// 4. Servo PWM Settings (LEDC Engine)
// ==========================================
#define PWM_FREQ          50
#define PWM_RESOLUTION    16
#define CHANNEL_PAN       0
#define CHANNEL_TILT      1

// Convert degrees (0-180) to 16-bit PWM duty cycle (50Hz)
uint32_t angleToDuty(int angle) {
  angle = constrain(angle, 0, 180);
  // 50Hz = 20ms period. Pulse 0.5ms (0 deg) to 2.5ms (180 deg)
  double pulse_us = 500.0 + (angle / 180.0) * 2000.0;
  return (uint32_t)((pulse_us / 20000.0) * 65535.0);
}

// Current and target servo positions for smooth easing
volatile int current_pan = 90, target_pan = 90;
volatile int current_tilt = 90, target_tilt = 90;

// ==========================================
// 5. I2S Initialization Functions
// ==========================================
void init_i2s_microphone() {
  i2s_config_t i2s_mic_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = MIC_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = AUDIO_CHUNK_SAMPLES,
    .use_apll = false
  };

  i2s_pin_config_t pin_mic = {
    .bck_io_num = PIN_I2S_MIC_SCK,
    .ws_io_num = PIN_I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = PIN_I2S_MIC_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_mic_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_mic);
}

void init_i2s_speaker() {
  i2s_config_t i2s_spk_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = SPK_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false
  };

  i2s_pin_config_t pin_spk = {
    .bck_io_num = PIN_I2S_SPK_BCLK,
    .ws_io_num = PIN_I2S_SPK_LRC,
    .data_out_num = PIN_I2S_SPK_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE
  };

  i2s_driver_install(I2S_NUM_1, &i2s_spk_config, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pin_spk);
}

// ==========================================
// 6. Facial Expressions (OLED Display)
// ==========================================
void draw_eyes(const char* emotion) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  
  if (strcmp(emotion, "happy") == 0) {
    // Upward curved eye arches
    display.drawCircle(40, 32, 16, SSD1306_WHITE);
    display.fillRect(20, 32, 40, 20, SSD1306_BLACK);
    display.drawCircle(88, 32, 16, SSD1306_WHITE);
    display.fillRect(68, 32, 40, 20, SSD1306_BLACK);
  } else if (strcmp(emotion, "listening") == 0) {
    // Wide curious circular eyes
    display.fillCircle(40, 32, 14, SSD1306_WHITE);
    display.fillCircle(88, 32, 14, SSD1306_WHITE);
  } else if (strcmp(emotion, "sleeping") == 0) {
    // Flat horizontal lines
    display.fillRect(26, 32, 28, 4, SSD1306_WHITE);
    display.fillRect(74, 32, 28, 4, SSD1306_WHITE);
  } else {
    // Default neutral eyes
    display.fillRoundRect(28, 20, 24, 26, 6, SSD1306_WHITE);
    display.fillRoundRect(76, 20, 24, 26, 6, SSD1306_WHITE);
  }
  display.display();
}

// ==========================================
// 7. WebSocket Event Dispatcher
// ==========================================
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("❌ [WS] Disconnected from Gateway.");
      break;

    case WStype_CONNECTED:
      Serial.println("✅ [WS] Connected to MAYA Gateway.");
      draw_eyes("happy");
      break;

    case WStype_BIN:
      // Direct raw audio PCM chunk from Gateway to Speaker DMA
      size_t bytes_written;
      i2s_write(I2S_NUM_1, payload, length, &bytes_written, portMAX_DELAY);
      break;

    case WStype_TEXT: {
      // Parse JSON hardware action command
      StaticJsonDocument<256> doc;
      DeserializationError err = deserializeJson(doc, payload);
      if (err) return;

      const char* action = doc["action"];

      if (strcmp(action, "relay") == 0) {
        int state = doc["state"];
        digitalWrite(PIN_RELAY, state ? HIGH : LOW);
        Serial.printf("⚡ [RELAY] State: %d\n", state);
      }
      else if (strcmp(action, "servo") == 0) {
        if (doc.containsKey("pan"))  target_pan  = doc["pan"];
        if (doc.containsKey("tilt")) target_tilt = doc["tilt"];
      }
      else if (strcmp(action, "oled") == 0) {
        const char* expr = doc["expression"];
        draw_eyes(expr);
      }
      else if (strcmp(action, "audio_flush") == 0) {
        // Immediate hardware buffer zeroing for instant barge-in cutoff
        i2s_zero_dma_buffer(I2S_NUM_1);
      }
      break;
    }
    default:
      break;
  }
}

// ==========================================
// 8. Core 1 Task: Servo Easing Engine
// ==========================================
void servoLoopTask(void* pvParameters) {
  while (true) {
    // Smooth linear interpolation to target angle (prevents sudden servo jerks)
    if (current_pan != target_pan) {
      current_pan += (target_pan > current_pan) ? 1 : -1;
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
      ledcWrite(PIN_SERVO_PAN, angleToDuty(current_pan));
#else
      ledcWrite(CHANNEL_PAN, angleToDuty(current_pan));
#endif
    }
    if (current_tilt != target_tilt) {
      current_tilt += (target_tilt > current_tilt) ? 1 : -1;
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
      ledcWrite(PIN_SERVO_TILT, angleToDuty(current_tilt));
#else
      ledcWrite(CHANNEL_TILT, angleToDuty(current_tilt));
#endif
    }
    vTaskDelay(pdMS_TO_TICKS(15)); // 15ms per step
  }
}

// ==========================================
// 9. Setup & Main Core 0 Loop
// ==========================================
void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, LOW); // Relay off on boot

  // Initialize OLED
  Wire.begin(I2C_SDA, I2C_SCL);
  display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  draw_eyes("sleeping");

  // Initialize LEDC PWM for Servos (handles Arduino ESP32 Core 2.x and 3.x)
#if ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
  ledcAttach(PIN_SERVO_PAN, PWM_FREQ, PWM_RESOLUTION);
  ledcWrite(PIN_SERVO_PAN, angleToDuty(90));

  ledcAttach(PIN_SERVO_TILT, PWM_FREQ, PWM_RESOLUTION);
  ledcWrite(PIN_SERVO_TILT, angleToDuty(90));
#else
  ledcSetup(CHANNEL_PAN, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_SERVO_PAN, CHANNEL_PAN);
  ledcWrite(CHANNEL_PAN, angleToDuty(90));

  ledcSetup(CHANNEL_TILT, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_SERVO_TILT, CHANNEL_TILT);
  ledcWrite(CHANNEL_TILT, angleToDuty(90));
#endif

  // Initialize I2S Audio Interfaces
  init_i2s_microphone();
  init_i2s_speaker();

  // Connect to Wi-Fi
  Serial.printf("Connecting to Wi-Fi: %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\n✅ Wi-Fi Connected! IP: " + WiFi.localIP().toString());

  // Launch Core 1 Servo Task
  xTaskCreatePinnedToCore(servoLoopTask, "ServoTask", 2048, NULL, 1, NULL, 1);

  // Initialize WebSocket Client
  webSocket.begin(SERVER_HOST, SERVER_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(2000);
}

void loop() {
  webSocket.loop();

  // Continuously capture audio from INMP441 and stream upstream
  if (webSocket.isConnected()) {
    size_t bytes_read = 0;
    i2s_read(I2S_NUM_0, mic_buffer, sizeof(mic_buffer), &bytes_read, portMAX_DELAY);
    if (bytes_read > 0) {
      webSocket.sendBIN(mic_buffer, bytes_read);
    }
  }
}
