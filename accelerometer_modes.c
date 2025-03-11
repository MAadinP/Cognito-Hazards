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

#include "sys/alt_stdio.h"

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

void int_to_str(int num, char *buf) {
    if (num == 0) {
        buf[0] = '0';
        buf[1] = '\0';
        return;
    }

    char temp[12];
    int i = 0;
    while (num > 0) {
        temp[i++] = '0' + (num % 10);
        num /= 10;
    }
    // Reverse the digits into the output buffer.
    int j;
    for (j = 0; j < i; j++) {
        buf[j] = temp[i - j - 1];
    }
    buf[i] = '\0';
}

// Custom function to convert a float to a string with a given precision.
// 'precision' is the number of digits after the decimal point.
void float_to_string_custom(float num, char *buf, int precision) {
    char *ptr = buf;

    // Handle negative numbers.
    if (num < 0) {
        *ptr++ = '-';
        num = -num;
    }

    // Separate the integer part.
    int int_part = (int)num;
    char int_buf[12];
    int_to_str(int_part, int_buf);

    // Copy the integer part into the output buffer.
    char *p = int_buf;
    while (*p) {
        *ptr++ = *p++;
    }

    // If precision is specified, process the fractional part.
    if (precision > 0) {
        *ptr++ = '.';
        float fractional = num - int_part;

        // Calculate multiplier for the required precision (10^precision).
        int multiplier = 1;
        for (int i = 0; i < precision; i++) {
            multiplier *= 10;
        }

        // Convert the fractional part to an integer (with rounding).
        int frac_int = (int)(fractional * multiplier + 0.5f);

        // Convert the fractional integer to string.
        char frac_buf[12];
        int_to_str(frac_int, frac_buf);

        // Determine the length of the fractional string.
        int len = 0;
        p = frac_buf;
        while (*p++) {
            len++;
        }

        // If the fractional part is shorter than the required precision,
        // pad with leading zeros.
        int pad = precision - len;
        while (pad-- > 0) {
            *ptr++ = '0';
        }

        // Copy the fractional part.
        p = frac_buf;
        while (*p) {
            *ptr++ = *p++;
        }
    }

    *ptr = '\0';
}

int main(void)
{
    alt_putstr("Duel Game\n");
    alt_32 x_read, y_read;
    float x_value, y_value, x_processed, y_processed;
    char x_str[32];
    char y_str[32];
    // alt_u8 out;
    alt_up_accelerometer_spi_dev * acc_dev;
    acc_dev = alt_up_accelerometer_spi_open_dev("/dev/accelerometer_spi");
    if (acc_dev == NULL) {
        alt_putstr("Error: Could not open accelerometer device\n");
        return 1;
    }

    timer_init(sys_timer_isr);

    int mode = 1;
   //  alt_printf("Default mode: %d (2 = calibration, 1 = filtering, 0 = raw)\n", mode);
   alt_printf("Default mode: %d (1 = filtering, 0 = raw)\n", mode);

    while (1) {

       int cmd = get_command_char();
       if (cmd != -1) {
            if (cmd == '0') {
                mode = 0;
//                alt_printf("Switched to Mode 0 (off).\n");
            }
            else if (cmd == '1') {
                mode = 1;
//                alt_printf("Switched to Mode 1 (filtering).\n");
            }
           //  else if (cmd == '2') {
           //     mode = 2;
           //     alt_printf("Switched to Mode 2 (calibration).\n");
           // }
            else if (cmd == 'q' || cmd == 'Q') {
                alt_putstr("Exiting...\n");
                break;
            }
            else {
            	mode = 0;
//                alt_printf("Unrecognized command: %c\n", cmd);
            }
        }

//       if (mode != 0) {
            if (mode == 1) {
                alt_up_accelerometer_spi_read_x_axis(acc_dev, &x_read);
                alt_up_accelerometer_spi_read_y_axis(acc_dev, &y_read);
            //    alt_printf("Raw data: %x\n", x_read);

                x_value = (float)x_read;
                x_processed = fir_filter(x_value);
                y_value = (float)y_read;
                y_processed = fir_filter(y_value);

                float_to_string_custom(x_processed, x_str, 3);
                float_to_string_custom(y_processed, y_str, 3);

                    // Use alt_printf to print the converted strings.
                    alt_printf("%s %s\n", x_str, y_str);

               // add the uart return data here
//                out = *level;
//                alt_putstring(out);
//                alt_putstr(std::tostring(processed_value));
//                alt_printf("Filtered x: %.2f\n", processed_value);

        //    }
           // else if (mode == 2) {
           //     // idk what we want for calibration at this stage but that goes here
           // }
       }

    }

    return 0;
}
