#if !defined(__TEMP_CONTROLLER_CPP__)
#define __TEMP_CONTROLLER_CPP__

#include "TempController.hpp"
#include "ApplicationDefines.h"

void TempController::Process() {
    switch (state)
    {
    case State::SETUP: {
        // Free the memory if it was allocated before
        if (results) delete[] results;
        if (devices) {
            for (int i = 0; i < device_count; i++)
                delete[] devices[i];
            delete[] devices;
        }
        device_count = 0;
        last_read_millis = 0;

        if (!ds.reset()) {
            static bool shown_error = false;
            if (!shown_error) {
                TC_PRINTLN("1-Wire bus not found!");
                shown_error = true;
            }
            return;
        }

        // Get the number of devices on the bus
        byte addr[8];
        ds.reset_search();
        while (ds.search(addr)) device_count++;

        if (device_count == 0) {
            static bool shown_error = false;
            if (!shown_error) {
                TC_PRINTLN("No 1-Wire devices found!");
                shown_error = true;
            }
            return;
        }

        // Allocate memory for the results
        results = new uint16_t[device_count];
        // Allocate memory for the addresses
        devices = new uint8_t*[device_count];
        for (int i = 0; i < device_count; i++) {
            results[i] = 0xFFFF;
            devices[i] = new uint8_t[8];
        }

        // Get the addresses of the devices
        ds.reset_search();
        for (int i = 0; i < device_count; i++)
        {
            ds.search(addr);
            for (int j = 0; j < 8; j++) devices[i][j] = addr[j];
        }

        state = State::START_CONVERSION;
        break;
    }
    case State::START_CONVERSION: {
        ds.reset();
        ds.skip();
        ds.write(0x44); // Start temperature conversion

        state = State::WAIT_CONVERSION;
        last_wait_millis = millis() + 500;
        break;
    }
    case State::WAIT_CONVERSION: {
        // Check if the conversion is done every 5ms
        unsigned long new_millis = millis();
        unsigned long ellapsed = new_millis - last_wait_millis;
        if (ellapsed < 5) return;
        last_wait_millis = new_millis;

        if (!ds.read_bit()) return;

        current_device = 0;
        crc_error_timeout = 0;
        state = State::READ;
        break;
    }
    case State::READ: {
        if (current_device >= device_count) {
            last_read_millis = millis();
            state = State::START_CONVERSION;
            return;
        }

        const uint8_t* addr = devices[current_device];
        ds.reset();
        ds.select(addr);
        ds.write(0xBE); // Read scratchpad
        // Read temperature
        byte data[9];
        for (int j = 0; j < 9; j++) data[j] = ds.read();
        // Check CRC
        if (OneWireFet::crc8(data, 8) != data[8]) {
            if (++crc_error_timeout > 10) {
                state = State::SETUP;
                TC_PRINTLN("CRC check error!");
            }
            return;
        }

        // Convert the data to actual temperature
        uint16_t raw = (data[1] << 8) | data[0];
        if (addr[0] == 0x10) {
            raw = raw << 3; // 9 bit resolution default
            if (data[7] == 0x10) raw = (raw & 0xFFF0) + 12 - data[6];
        } else {
            byte cfg = (data[4] & 0x60);
            if (cfg == 0x00) raw = raw & ~7;  // 9 bit resolution, 93.75 ms
            else if (cfg == 0x20) raw = raw & ~3; // 10 bit res, 187.5 ms
            else if (cfg == 0x40) raw = raw & ~1; // 11 bit res, 375 ms
        }
        results[current_device] = raw;

        crc_error_timeout = 0;
        current_device++;
        break;
    }
    default:
        state = State::SETUP;
    }
}

#endif // __TEMP_CONTROLLER_CPP__
