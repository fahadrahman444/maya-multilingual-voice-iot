#include <Arduino.h>
#include <driver/i2s.h>
#include <Wire.h>

// ==========================================
// 1. Pin Definitions (ESP32-S3 N16R8)
// ==========================================
#define PIN_I2S_MIC_SD    4
#define PIN_I2S_MIC_WS    5
#define PIN_I2S_MIC_SCK   6

#define PIN_SERVO_PAN     13
#define PIN_SERVO_TILT    14
#define PIN_RELAY         21

#define I2C_SDA           8
#define I2C_SCL           9

#define SAMPLE_RATE       16000
#define CHUNK_SAMPLES     256

int32_t raw_i2s[CHUNK_SAMPLES];
int16_t pcm16[CHUNK_SAMPLES];
bool isRecording = false;

// ==========================================
// 2. I2S Setup for INMP441 (16kHz Mono)
// ==========================================
void init_i2s_mic() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT, // INMP441 requires 32-bit slot
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = PIN_I2S_MIC_SCK,
    .ws_io_num = PIN_I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = PIN_I2S_MIC_SD
  };

  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

void setup() {
  Serial.begin(115200);
  
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, LOW);

  init_i2s_mic();
  delay(200);
  Serial.println("\nMAYA_AUDIO_BRIDGE_READY");
}

void loop() {
  // Check for commands from Maya Python Core
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'R') {
      // START STREAMING AUDIO
      isRecording = true;
      i2s_zero_dma_buffer(I2S_NUM_0);
    } else if (cmd == 'S') {
      // STOP STREAMING AUDIO
      isRecording = false;
    } else if (cmd == '1') {
      digitalWrite(PIN_RELAY, HIGH);
    } else if (cmd == '0') {
      digitalWrite(PIN_RELAY, LOW);
    }
  }

  // Stream raw 16-bit PCM whenever recording is active
  if (isRecording) {
    size_t bytes_read = 0;
    i2s_read(I2S_NUM_0, raw_i2s, sizeof(raw_i2s), &bytes_read, 20);
    if (bytes_read > 0) {
      int samples = bytes_read / 4;
      for (int i = 0; i < samples; i++) {
        // Shift 24-bit audio in 32-bit slot down to 16-bit signed PCM
        pcm16[i] = (int16_t)(raw_i2s[i] >> 14);
      }
      Serial.write((const uint8_t*)pcm16, samples * sizeof(int16_t));
    }
  } else {
    delay(5);
  }
}
