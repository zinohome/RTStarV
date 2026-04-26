#include "rtstarv_imu.h"
#include "usb_device.h"
#include "imu_reader.h"
#include "attitude_solver.h"
#include <memory>

static std::unique_ptr<rtstarv::UsbDevice> g_device;
static std::unique_ptr<rtstarv::ImuReader> g_reader;
static std::unique_ptr<rtstarv::AttitudeSolver> g_solver;

static rtstarv::FreqCode hz_to_code(int freq_hz) {
    switch (freq_hz) {
        case 200: return rtstarv::FreqCode::Hz200;
        case 100: return rtstarv::FreqCode::Hz100;
        case 50:  return rtstarv::FreqCode::Hz50;
        case 25:  return rtstarv::FreqCode::Hz25;
        default:  return rtstarv::FreqCode::Hz12_5;
    }
}

extern "C" {

int rtstarv_init(void) {
    if (g_device && g_device->is_open()) return 0;

    g_device = std::make_unique<rtstarv::UsbDevice>();
    if (!g_device->open()) {
        g_device.reset();
        return -1;
    }
    g_reader = std::make_unique<rtstarv::ImuReader>(*g_device);
    g_solver = std::make_unique<rtstarv::AttitudeSolver>();
    return 0;
}

void rtstarv_shutdown(void) {
    if (g_reader) g_reader->stop();
    g_reader.reset();
    g_solver.reset();
    if (g_device) g_device->close();
    g_device.reset();
}

int rtstarv_is_connected(void) {
    return (g_device && g_device->is_open()) ? 1 : 0;
}

int rtstarv_start(int freq_hz, int enable_mag) {
    if (!g_reader) return -1;
    return g_reader->start(hz_to_code(freq_hz), enable_mag != 0) ? 0 : -1;
}

void rtstarv_stop(void) {
    if (g_reader) g_reader->stop();
}

int rtstarv_get_imu(RTStarVImuData* out) {
    if (!out || !g_reader) return -1;

    rtstarv::ImuSample s;
    if (!g_reader->get_latest(s)) return -1;

    // 同时更新姿态解算
    if (g_solver) g_solver->update(s);

    out->acc_x = s.acc_x;  out->acc_y = s.acc_y;  out->acc_z = s.acc_z;
    out->gyr_x = s.gyr_x;  out->gyr_y = s.gyr_y;  out->gyr_z = s.gyr_z;
    out->timestamp = s.timestamp;
    out->sequence = s.sequence;
    out->has_mag = s.has_mag ? 1 : 0;
    out->mag_x = s.mag_x;  out->mag_y = s.mag_y;  out->mag_z = s.mag_z;
    out->mag_timestamp = s.mag_timestamp;
    return 0;
}

int rtstarv_get_attitude(RTStarVAttitude* out) {
    if (!out || !g_solver) return -1;

    auto a = g_solver->get();
    out->yaw = a.yaw;
    out->pitch = a.pitch;
    out->roll = a.roll;
    return 0;
}

void rtstarv_recenter(void) {
    if (g_solver) g_solver->recenter();
}

uint32_t rtstarv_dropped_frames(void) {
    return g_reader ? g_reader->dropped_frames() : 0;
}

} // extern "C"
