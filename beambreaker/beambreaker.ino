

int bb_pins[9] = {7, 2, 3, 4, 5, 8, 9, 13, 12};
int bb_last[9] = {0, 0, 0, 0, 0, 0, 0, 0, 0};


int checkBeamBreaker(int bb, int pin, int bblast) {
  // read the state of the pushbutton value:

  int state = digitalRead(pin);
  if (state == 0 and bblast != 1) {
    Serial.println(bb);
    return 1;
  } else if (state == 1 and bblast == 1) {
    return 0;
  } else{
    return bblast;
  }
}

void setup() {
  // initialize the sensor pin as an input:
  for (int i=0; i<9; i++) {
    pinMode(bb_pins[i], INPUT);     
    digitalWrite(bb_pins[i], HIGH); // turn on the pullup
  }

  Serial.begin(9600);
}

void loop(){
  // read the state of the pushbutton value:
  // bb_last[0] = checkBeamBreaker(1, bb_pins[0], bb_last[0]);
  for (int i=0; i<9; i++) {
    bb_last[i] = checkBeamBreaker(i+1, bb_pins[i], bb_last[i]);
  }
  
}
