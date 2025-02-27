/*
 * Integrated Accelerometer and Command Processing Example
 *
 * This application integrates a simple JTAG UART command interface (based on
 * the provided example code) with an accelerometer reading project (Lab 3).
 * It supports two modes:
 *    Mode 0: No filtering – use raw accelerometer data.
 *    Mode 1: Use a FIR filter to filter the accelerometer data.
 *
 * Commands (sent via JTAG UART):
 *    '0' : switch to Mode 0 (no filtering)
 *    '1' : switch to Mode 1 (filtering)
 *    'q' : quit (stop processing, if desired)
 *
 * The application polls both the accelerometer and the JTAG UART. Since the
 * Nios II is polling the JTAG, you should consider the polling frequency so
 * that the accelerometer is sampled often enough.
 *
 * Compile with the appropriate Nios II system libraries.
 */

 #include <stdio.h>
 #include <stdlib.h>
 #include <string.h>
 #include <math.h>
 #include "system.h"
 #include "altera_up_avalon_accelerometer_spi.h"
 #include "altera_avalon_timer_regs.h"
 #include "altera_avalon_timer.h"
 #include "altera_avalon_pio_regs.h"
 #include "sys/alt_irq.h"
 #include "sys/times.h"
 #include "alt_types.h"
 
 #define FILTER_ORDER 50  
 
 // this will need tuning for the game
 static float coeffs[FILTER_ORDER] = {
     0.0046f,  0.0074f, -0.0024f, -0.0071f,  0.0033f,  0.0001f, -0.0094f,  0.0040f,  0.0044f,
    -0.0133f,  0.0030f,  0.0114f, -0.0179f, -0.0011f,  0.0223f, -0.0225f, -0.0109f,  0.0396f,
    -0.0263f, -0.0338f,  0.0752f, -0.0289f, -0.1204f,  0.2879f,  0.6369f,  0.2879f, -0.1204f,
    -0.0289f,  0.0752f, -0.0338f, -0.0263f,  0.0396f, -0.0109f, -0.0225f,  0.0223f, -0.0011f,
    -0.0179f,  0.0114f,  0.0030f, -0.0133f,  0.0044f,  0.0040f, -0.0094f,  0.0001f,  0.0033f,
    -0.0071f, -0.0024f,  0.0074f,  0.0046f
 };
 
 float fir_filter(float new_sample)
 {
     static float buffer[FILTER_ORDER] = {0.0f};
     static int index = 0;
 
     float output = 0.0f;
     int i, j;
 
     buffer[index] = new_sample;
 
     j = index;
     for (i = 0; i < FILTER_ORDER; i++) {
         output += buffer[j] * coeffs[i];
         j--;
         if (j < 0)
             j = FILTER_ORDER - 1;
     }
 
     index++;
     if (index >= FILTER_ORDER)
         index = 0;
 
     return output;
 }

 #define OFFSET -32
 #define PWM_PERIOD 16
 
 alt_8 pwm = 0;
 alt_u8 led;
 int level;
 
 void led_write(alt_u8 led_pattern) {
     IOWR(LED_BASE, 0, led_pattern);
 }
 
 void convert_read(alt_32 acc_read, int *level, alt_u8 *led) {
     acc_read += OFFSET;
     alt_u8 val = (acc_read >> 6) & 0x07;
     *led = (8 >> val) | (8 << (8 - val));
     *level = (acc_read >> 1) & 0x1f;
 }
 
 void sys_timer_isr(void* context)
 {
     IOWR_ALTERA_AVALON_TIMER_STATUS(TIMER_BASE, 0);
 
     if (pwm < abs(level)) {
         if (level < 0)
             led_write(led << 1);
         else
             led_write(led >> 1);
     } else {
         led_write(led);
     }
 
     if (pwm > PWM_PERIOD)
         pwm = 0;
     else
         pwm++;
 }
 
 void timer_init(void* isr)
 {
     IOWR_ALTERA_AVALON_TIMER_CONTROL(TIMER_BASE, 0x0003);
     IOWR_ALTERA_AVALON_TIMER_STATUS(TIMER_BASE, 0);
     IOWR_ALTERA_AVALON_TIMER_PERIODL(TIMER_BASE, 0x0900);
     IOWR_ALTERA_AVALON_TIMER_PERIODH(TIMER_BASE, 0x0000);
     alt_irq_register(TIMER_IRQ, 0, isr);
     IOWR_ALTERA_AVALON_TIMER_CONTROL(TIMER_BASE, 0x0007);
 }

 int get_command_char(void)
 {
     int ch = alt_getchar();
     if (ch == -1)
         return -1;
     return ch;
 }
 
 int main(void)
 {
     alt_putstr("Duel Game\n");
     alt_32 x_read;
     alt_up_accelerometer_spi_dev * acc_dev;
     acc_dev = alt_up_accelerometer_spi_open_dev("/dev/accelerometer_spi");
     if (acc_dev == NULL) { 
         alt_putstr("Error: Could not open accelerometer device\n");
         return 1;
     }
 
     timer_init(sys_timer_isr);
 
     int mode = 1;  
     alt_printf("Default mode: %d (2 = calibration, 1 = filtering, 0 = raw)\n", mode);
 
     while (1) {
 
        int cmd = get_command_char();
        if (cmd != -1) {
             if (cmd == '0') {
                 mode = 0;
                 alt_printf("Switched to Mode 0 (off).\n");
             }
             else if (cmd == '1') {
                 mode = 1;
                 alt_printf("Switched to Mode 1 (filtering).\n");
             }
             else if (cmd == '2') {
                mode = 2;
                alt_printf("Switched to Mode 2 (calibration).\n");
            }
             else if (cmd == 'q' || cmd == 'Q') {
                 alt_putstr("Exiting...\n");
                 break;
             }
             else {
                 alt_printf("Unrecognized command: %c\n", cmd);
             }
         }
 
        if (mode != 0) {
            if (mode == 1) {
                alt_up_accelerometer_spi_read_x_axis(acc_dev, &x_read);
                alt_printf("Raw data: %d\n", x_read);
        
                float x_value = (float)x_read;
                float processed_value = x_value;

                processed_value = fir_filter(x_value);
                alt_printf("Filtered x: %.2f\n", processed_value);

                convert_read((alt_32)processed_value, &level, &led);

                // add the uart return data here
            }
            else if (mode == 2) {
                // idk what we want for calibration at this stage but that goes here 
            }
        }
 
     }
 
     return 0;
 }
 