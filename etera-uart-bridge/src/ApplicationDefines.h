#ifndef __APPLICATION_DEFINES_H__
#define __APPLICATION_DEFINES_H__

#define MOTOR_1L_PIN  (A0)
#define MOTOR_1D_PIN  (A1)
#define MOTOR_2L_PIN  (A2)
#define MOTOR_2D_PIN  (A3)
#define MOTOR_3L_PIN  (A4)
#define MOTOR_3D_PIN  (A5)
#define MOTOR_4L_PIN  (13)
#define MOTOR_4D_PIN  (11)
#define ONEWIRE_BUS_READ_PIN   (10)
#define ONEWIRE_BUS_WRITE_PIN  (12)
#define EXPANDER_PIN_START  (2)

#define TC_PRINT_START() Serial.print("\xEA")
#define TC_PRINT_END()   Serial.print("\xEB")
#define TC_PRINTLN(x) TC_PRINT_START(); Serial.println(x); TC_PRINT_END()

#endif // __APPLICATION_DEFINES_H__