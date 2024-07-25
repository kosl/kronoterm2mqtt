#if !defined(__TEMP_CONTROLLER_HPP__)
#define __TEMP_CONTROLLER_HPP__

#include <OneWireFet.hpp>
#include "ApplicationDefines.h"
#include <Arduino.h>

class TempController
{
public:
    void Process();

    uint8_t GetDeviceCount()
    { return device_count; }
    uint16_t GetTempature(uint8_t device)
    {
        if (device < device_count)
            return results[device];
        return -1;
    }
    uint8_t* GetAddress(uint8_t device)
    {
        if (device < device_count)
            return devices[device];
        return nullptr;
    }

    unsigned long GetLastReadMillis()
    { return last_read_millis; }

    ~TempController()
    {
        for (int i = 0; i < device_count; i++)
            delete[] devices[i];
        if (devices) delete[] devices;
        if (results) delete[] results;
    }

private:
    OneWireFet ds {ONEWIRE_BUS_READ_PIN, ONEWIRE_BUS_WRITE_PIN};
    enum class State
    {
        SETUP,
        START_CONVERSION,
        WAIT_CONVERSION,
        READ
    } state = State::SETUP;

    //! Total number of temperature sensors on the bus
    uint8_t device_count = 0;
    //! Array of addresses of the devices on the bus
    uint8_t** devices = nullptr;
    //! Current device being read
    uint8_t current_device = -1;
    //! All conversion results
    uint16_t* results = nullptr;

    //! Last read temperature
    unsigned long last_read_millis = 0;

    //! Wait conversion timeout
    unsigned long last_wait_millis = 0;
    //! Read CRC error timeout
    uint8_t crc_error_timeout = 0;
};

#endif // __TEMP_CONTROLLER_HPP__
