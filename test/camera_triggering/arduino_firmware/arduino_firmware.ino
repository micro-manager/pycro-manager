int OUT_PIN = 6;
int OUT_LED = 4; 

void setup() {
  // put your setup code here, to run once:
  pinMode(OUT_PIN, OUTPUT);
  pinMode(OUT_LED, OUTPUT);
  digitalWrite(OUT_PIN, LOW);
  digitalWrite(OUT_LED, LOW);
  Serial.begin(9600);
}

void loop() {
  if (Serial.available() > 0) {
    int d = Serial.parseInt();
    digitalWrite(OUT_PIN, HIGH);
    digitalWrite(OUT_LED, HIGH);
    delay(d);
    digitalWrite(OUT_PIN, LOW);
    digitalWrite(OUT_LED, LOW);
  }

}

// The old script

// int TRIGGER_OUT_LED = 3;
// int TRIGGER_OUT = 8;
// int TRIGGER_IN_LED = 2;
// int TRIGGER_IN = 11;

// volatile long triggerInStart_us = -1;
// volatile long triggerInEnd_us = -1;

// void setup() {
//   pinMode(TRIGGER_OUT, OUTPUT);
//   pinMode(TRIGGER_OUT_LED, OUTPUT);
//   // pinMode(TRIGGER_IN, INPUT);
//   // pinMode(TRIGGER_IN_LED, OUTPUT);
//   Serial.begin(9600);
//   digitalWrite(TRIGGER_OUT, LOW);
//   digitalWrite(TRIGGER_OUT_LED, LOW);
//   // digitalWrite(TRIGGER_IN_LED, LOW);
//   // attachInterrupt(digitalPinToInterrupt(TRIGGER_IN), triggerInHigh, RISING);
//   // attachInterrupt(digitalPinToInterrupt(TRIGGER_IN), triggerInLow, FALLING);
// }

// void triggerInHigh() {
//     triggerInStart_us = micros();
//     digitalWrite(TRIGGER_IN_LED, HIGH);
// }

// void triggerInLow() {
//     triggerInEnd_us = micros();
//     digitalWrite(TRIGGER_IN_LED, LOW);
// }

// void sendTrigger(long duration_ms) {
//   digitalWrite(TRIGGER_OUT, HIGH);
//   digitalWrite(TRIGGER_OUT_LED, HIGH);
//   delay(duration_ms);
//   digitalWrite(TRIGGER_OUT, LOW);
//   digitalWrite(TRIGGER_OUT_LED, LOW);
// }

// void loop() {
// sendTrigger(2000);
// delay(2000);

//   // if (Serial.available()) {
//   //   long triggerDuration = Serial.parseInt();  //read until timeout
//   //   sendTrigger(triggerDuration);
//   // } else if (triggerInEnd_us != -1) {
//   //   long triggerLength = triggerInEnd_us - triggerInStart_us;
//   //   Serial.write(triggerLength);
//   //   triggerInEnd_us = -1;
//   //   triggerInStart_us = -1;
//   // }

// }
