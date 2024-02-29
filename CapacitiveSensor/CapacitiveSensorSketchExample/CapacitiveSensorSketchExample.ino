/*
 * CapacitiveSense Library Demo Sketch
 * A reset of the reference is done if the previous values are under a threshold
 * 
 * A reset is only possible when the in-progress iteration is an integer multiple of a certain values to prevent from
 * a reset at every iteration when no contact is made.
 * 
 *
 * A 2 megaohm resistor was used in the RC circuit to get a touch sensor only.
 * Look at the guide in the github repo to change sensitivity
 * Nathan Bérubé, August 2023
 */
#include <CapacitiveSensor.h>


const bool print = true; // variable used to determine if print readings (true will slow down execution)
bool reset_plate = false; // variable acting as a switch for the reset of the sensor
int i = 0; // variable used to keep track of iterations
const int reset_trigg_value_plate = 0; // capacity treshold considered as "no-contact" to trigger reset of the sensor
const int reset_num_older_value = 40; // number of old value used to determine the stability needed to trigger the reset of the sensor

int previous_values_plate[reset_num_older_value];

CapacitiveSensor   plate = CapacitiveSensor(2,13);        // (emitting pin, sensing pin)

void setup()                    
{ 
  Serial.begin(115200);
  plate.reset_CS_AutoCal(); // set the new reference of the plate
  // plate.set_CS_AutocaL_Millis(0xFFFFFFFF); // disable the auto reset of reference of the plate
  Serial.println("Starting...");
}

void loop() {
  int total_plate = plate.capacitiveSensor(10); // read the capacitance value

  // place the reading in the array of previous values at the position of the older value
  if (reset_plate){
    previous_values_plate[i%reset_num_older_value] = total_plate;

    // for every value in the previous values
    for (int index = 0; index < reset_num_older_value; index++){
    // verify if the value is below the threshold
      if (previous_values_plate[index] > reset_trigg_value_plate){
        reset_plate = false; // cancel reset
        break;               // stop verifying other values
      }
      else reset_plate = true; // if all previous values are below value, reset is possible
    }
  }
  // verify if the previous values are under the threshold AND the in-progress iteration is an integer multiple 
  // of the number of previous values looked at AND the in-progress iteration is bigger than the size of the previous values array
  if (reset_plate && i%reset_num_older_value == 0 && i >= reset_num_older_value){
    plate.reset_CS_AutoCal();   //reset the sensor
    Serial.println();
    Serial.println("            * * * * * * * * * * RESET * * * * * * * * * *");
    Serial.println();
  }

  // print parameters to vizualize data acquisition
  if (print){    
    Serial.print("Plate contact:  ");  
    if (total_plate > reset_trigg_value_plate) {
      Serial.print("Yes      ");
    }
    else {        
      Serial.print("No      ");
    }
    Serial.print("Value:    ");
    Serial.println(total_plate);

  i++; // add one to the iteration variable
  delay(10);
  }
}

