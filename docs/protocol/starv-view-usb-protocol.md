# StarV View USB HID Protocol — Reverse Engineering Findings

> Source: `libsv_hid.so` (457KB ARM64, SunnyVerse SDK)  
> Date: 2026-04-26  
> Status: Confirmed via static binary analysis (no live device validation yet)

---

## 1. USB Device Identity

| Field | Value | Confidence |
|-------|-------|------------|
| Vendor ID | 0x2A45 | **Confirmed** (Meizu) |
| Product ID | 0x2050 | **Confirmed** |
| SDK | SunnyVerse USB HID (shared with Xreal Air) |
| Build origin | Embedded build path confirms SunnyVerse SDK |

## 2. USB Topology

### Endpoints

| Endpoint | Direction | Type | Role |
|----------|-----------|------|------|
| 0x03 | OUT | Interrupt | Command TX |
| 0x81 | IN 1 | Interrupt | Response / Data RX |
| 0x83 | IN 3 | Interrupt | Data RX |
| 0x85 | IN 5 | Interrupt | Data RX |

- All transfers use `libusb_interrupt_transfer` (sync) for TX or async callback for RX
- TX timeout: 2000ms
- Packet size: **64 bytes** (all directions)

### Interface Claim

The SDK claims USB interface **3** or **4** (conditional logic at `0x64e90`):
- Checks if interface number == 4, then claims
- Else checks if interface number == 3, then claims
- This matches Xreal Air (interface 3 = IMU, interface 4 = MCU)

**Candidate**: Interface 3 for IMU data, interface 4 for MCU commands. Needs live device enumeration to confirm actual interface numbers exposed by StarV View.

## 3. Packet Format

### Universal Header

All packets start with magic byte `0x42` ('B'). The first 8 bytes form the packet header:

```
Offset  Field           Notes
0       magic           Always 0x42
1       sub_type_1      Varies by packet type
2       sub_type_2      Varies by packet type
3       field_3         Varies
4       category        Major packet type selector
5       sub_category    Sub-type within category
6       field_6         Varies
7       field_7         Varies
8-63    payload         Type-specific data
```

### Packet Type Dispatch Table

Extracted from `sv_libusb_parse_data` (0x5be30, 21KB):

| Byte Pattern | Category | Description | Callback Type |
|-------------|----------|-------------|---------------|
| `42 00 08 05 01 02 FF` | IMU 9DOF Raw | Accel + Gyro + Mag | type=2 |
| `42 __ __ __ 08 04` | Command Response A | Panel status etc. | type=4 |
| `42 __ __ 08 02 0E` | IMU Internal | 6DOF IMU data | type=2, tag=`sv_hid_imu_internal` |
| `42 __ __ 03 02/11 __` | Config Data | Configuration response | type=0 |
| `42 __ __ __ 07 03 03 11/12/13` | IMU Extended | 9DOF with variant ID | type=0x26 |
| `42 __ __ __ 07 02` | IMU Variant B | 7-axis variant | type=2 |
| `42 __ __ __ 07 01` | IMU Variant C | Minimal IMU | type=2 |
| **`42 __ __ __ 01 06`** | **IMU Primary (9DOF)** | **Main IMU stream** | **type=1** |
| **`42 __ __ __ 01 02`** | **IMU Primary (6DOF)** | **Main IMU stream (no mag)** | **type=2** |
| `42 __ __ __ 06 03` | Sensor Data A | Auxiliary sensor | varies |
| `42 __ __ __ 02 07` | Sensor Data B | Auxiliary sensor | varies |
| `42 __ __ __ 29 01 06 02` | Extended Data A | 4-field match | varies |
| `42 __ __ __ 29 01 04 10` | Extended Data B | 4-field match | varies |
| `42 __ __ __ 29 01 04 11` | Extended Data C | 4-field match | varies |

### IMU Data Packet (Primary)

The main IMU stream uses packets matching `byte[4]==0x01`. Two sub-category values are dispatched:

```
byte[0] = 0x42  (magic)
byte[4] = 0x01
byte[5] = 0x06  → callback type=1
byte[5] = 0x02  → callback type=2
```

**Note**: Both sub-categories route to the same handler at `0x5c750` via the dispatch table. The `type=1` vs `type=2` distinction may control downstream processing (e.g., whether magnetometer fields are populated), but the raw parsing path is shared. The "9DOF vs 6DOF" interpretation is **speculative** — needs live packet capture to confirm whether byte[5] correlates with magnetometer presence.

### IMU Sensor Data Layout

From `sv_libusb_receive_data` (0x61084), the parsed structure contains:

| Struct Offset | Type | Field |
|--------------|------|-------|
| 0x4E | uint8 | Frame sequence / packet ID |
| 0x4F | uint8 | Status flags (bit fields: bit6-7, bit5, bit4, bit2, bit1, bit0) |
| 0x50 | float32 | **acc_x** (m/s²) |
| 0x54 | float32 | **acc_y** |
| 0x58 | float32 | **acc_z** |
| 0x5C | float32 | **gyr_x** (rad/s) |
| 0x60 | float32 | **gyr_y** |
| 0x64 | float32 | **gyr_z** |
| 0x68 | uint32 | Timestamp low (device clock) |
| 0x6C | uint32 | Timestamp high or secondary |

For 9DOF packets, magnetometer data is also present:
| Struct Offset | Type | Field |
|--------------|------|-------|
| fp-0x78 | float32 | **mag_x** |
| fp-0x74 | float32 | **mag_y** |
| fp-0x70 | float32 | **mag_z** |

**IMPORTANT**: These offsets are within the PARSED structure, not the raw USB packet. The raw 64-byte packet is embedded at **offset 0x68** (or 0x8c in some code paths) within the structure. The byte→float conversion happens in a callback function invoked via function pointer (address in GOT at 0x74768/0x74780).

### Raw Packet ↔ Structure Mapping (SPECULATIVE)

> **⚠ This table is extrapolation, not a RE finding.** We know the parsed *structure* stores floats at offsets 0x50-0x6C (4 bytes apart), but the mapping from raw USB bytes to those struct fields passes through a callback function pointer (GOT 0x74768/0x74780) that has not been fully traced. The layout below is a plausible guess based on Xreal Air analogy and dense packing — **it must be validated against live packet captures**.

```
Raw USB Packet (64 bytes) — SPECULATIVE:
[0]      0x42 magic                        ← CONFIRMED
[1-3]    sub-type fields                   ← CONFIRMED (dispatch keys)
[4]      category (0x01 for IMU)           ← CONFIRMED
[5]      sub-category (0x06 or 0x02)       ← CONFIRMED
[6-7]    unknown (frame ID?)               ← SPECULATIVE
[8-11]   acc_x (float32 LE)?              ← SPECULATIVE
[12-15]  acc_y (float32 LE)?
[16-19]  acc_z (float32 LE)?
[20-23]  gyr_x (float32 LE)?
[24-27]  gyr_y (float32 LE)?
[28-31]  gyr_z (float32 LE)?
[32-35]  mag_x (float32 LE)?
[36-39]  mag_y (float32 LE)?
[40-43]  mag_z (float32 LE)?
[44-51]  timestamp (uint64 LE)?
[52-63]  unknown
```

**What IS confirmed from binary analysis:**
- Sensor values are **float32 IEEE 754** (fcvt s→d instructions, %f format strings)
- Parsed struct stores 6 sensor floats at 4-byte intervals (offsets 0x50-0x64)
- Raw 64-byte USB packet is embedded at offset 0x68 (or 0x8c) within the parsed struct
- A callback function converts raw bytes → struct floats (pointer not yet resolved)

**What needs live validation:**
- Exact byte positions of sensor data within the 64-byte raw packet
- Whether the callback does any transformation (scale, reorder, coordinate flip)

## 4. Command Protocol

### Command Sending

Commands go through `sv_hid_setHmdCmd` (0x687c8) → `Sys_HID_SendData` (0x67634) → `libusb_interrupt_transfer(handle, EP 0x03, buf, len, &transferred, 2000ms)`.

Each command has a numeric ID that maps to a specific packet length via a switch-case:

| Length (bytes) | Hex |
|---------------|-----|
| 7 | 0x07 |
| 8 | 0x08 |
| 9 | 0x09 |
| 10 | 0x0a |
| 11 | 0x0b |
| 13 | 0x0d |
| 14 | 0x0e |
| 35 | 0x23 |
| 42 | 0x2a |
| 43 | 0x2b |
| 63 | 0x3f |
| 64 | 0x40 |

Variable-length commands (IDs 0x39, 0x41, 0x52) go through `sv_hid_setHmdCmd_ext` (0x686f0).

### Command ID Map

| ID | Function | Description |
|----|----------|-------------|
| 0x08 | sv_hid_set_both_brightness | Set display brightness |
| 0x09 | sv_hid_set_2D3D_state | Switch 2D/3D display mode |
| 0x11 | sv_hid_switch_display_style_mode | Display style |
| 0x13 | sv_hid_set_ps_sensor | Proximity sensor control |
| 0x20 | sv_hid_set_imu_frequency | Set IMU sample rate |
| 0x23 | sv_hid_control_mic | Microphone control |
| 0x24 | sv_hid_control_pa | Power amplifier control |
| 0x25 | sv_hid_control_audio | Audio control |
| 0x26 | sv_hid_long_press | Long press behavior |
| 0x36 | sv_hid_calibration_p_sensor | Proximity sensor calibration |
| 0x39 | sv_hid_set_sn | Set serial number (var len) |
| 0x41 | sv_hid_set_device_name | Set device name (var len) |
| 0x47 | sv_hid_set_sleep | Sleep mode control |
| 0x48 | sv_hid_get_current_sleep | Get current sleep state |
| 0x49 | sv_hid_set_screen | Screen on/off |
| 0x50 | sv_hid_get_screen | Get screen state |
| 0x51 | sv_hid_get_sn_extend | Get extended serial number |
| 0x52 | sv_hid_set_sn_extend | Set extended SN (var len) |
| 0x55 | sv_hid_set_log_trigger | Trigger log output |
| 0x59 | sv_hid_set_sleep_timeout | Set sleep timeout |
| 0x5b | sv_hid_resume_deep_sleep | Resume from deep sleep |
| 0x5e | sv_hid_save_geomagnetic | Save magnetometer calibration |
| 0x5f | sv_hid_get_screen_rotation | Get screen rotation |
| 0x60 | sv_hid_save_screen_rotation | Save screen rotation |
| 0x61 | sv_hid_set_accel_scale | Set accelerometer scale |
| 0x63 | sv_hid_set_gyro_scale | Set gyroscope scale |
| 0x65 | sv_hid_set_accel_misalignment | Accel misalignment matrix |
| 0x67 | sv_hid_set_gyro_misalignment | Gyro misalignment matrix |
| 0x69 | sv_hid_set_bias_imu | Set IMU bias offsets |
| **0x6d** | **sv_hid_open_hid_data** | **Enable/disable IMU stream** |
| 0x6e | sv_hid_set_esd_mode | ESD protection mode |
| 0x71 | sv_hid_set_screen_color | Set screen color |
| 0x72 | sv_hid_get_screen_color | Get screen color |

### IMU Enable Command (0x6d)

```c
// To enable IMU streaming:
sv_hid_open_hid_data(1);  // arg=1 enable, arg=0 disable

// Internally sends cmd 0x6d via sv_hid_getHmdCmdData()
// which sends the command AND waits for a response
// The enable flag is stored at byte offset within the command buffer
```

From `sv_hid_open_hid_data` (0x4db04):
1. Constructs a 64-byte command buffer (zeroed)
2. Sets enable flag at a specific byte offset
3. Copies template data from buffer_open_hid_data (BSS at 0x73dac)
4. Calls `sv_hid_getHmdCmdData(global_ctx, 0x6d, buffer)`
5. Waits for response via pthread_cond_timedwait

## 5. Initialization Sequence

From `sv_hid_init` → `sv_hid_start` → `sv_libusb_hid_init`:

1. `sv_hid_init(fd)` — stores file descriptor, sleeps 100ms
2. `sv_hid_start()` — logs SDK version, spawns worker pthread
3. Worker thread calls `sv_libusb_hid_init(fd)`:
   a. `libusb_init()` — initialize libusb context
   b. `libusb_set_option(ctx, LIBUSB_OPTION_LOG_LEVEL, 2)` — set debug level
   c. `libusb_open_fd(ctx, fd, &handle)` — open via Android file descriptor
   d. `libusb_has_capability(CAP_HAS_HOTPLUG)` — check capability
   e. Enumerate interfaces, claim interface **3 or 4**
   f. `sv_libusb_hid_loop()` — set up async transfers on EP 0x81, 0x83, 0x85

4. To start IMU data:
   - Call `sv_hid_open_hid_data(1)` → sends cmd 0x6d

## 6. Cross-Reference: Xreal Air Protocol

StarV View and Xreal Air share the same SunnyVerse SDK. Key similarities and differences:

| Feature | Xreal Air | StarV View |
|---------|-----------|------------|
| SDK | SunnyVerse | SunnyVerse |
| IMU enable cmd | 0x19 | **0x6d** |
| Packet magic | 0xAA | **0x42** |
| Packet size | 64 bytes | 64 bytes |
| IMU signature | {0x01, 0x02} | byte[4]=0x01, byte[5]=0x02 |
| Sensor format | 3-byte signed int + scale | **float32 IEEE 754** |
| Sample rate | ~1000 Hz | Unknown (configurable via cmd 0x20) |
| Endpoints | Similar IN 0x81/0x83 | IN 0x81/0x83/0x85 |

**Key difference**: StarV View appears to send pre-computed float32 values rather than raw integer ADC readings. This simplifies the driver significantly — no need for multiplier/divisor scaling.

## 7. Key Functions Reference

| Address | Name | Size | Role |
|---------|------|------|------|
| 0x41ea4 | sv_hid_init_hmd_cmd | 6316B | Initialize all command buffer templates |
| 0x4db04 | sv_hid_open_hid_data | 964B | Enable/disable IMU data stream |
| 0x5be30 | sv_libusb_parse_data | 21076B | Parse incoming USB packets |
| 0x61084 | sv_libusb_receive_data | ~3500B | Process parsed IMU data, write to file |
| 0x61ed0 | sv_libusb_receive_cmd_data | ~10KB | Process command responses |
| 0x65de0 | sv_libusb_hid_loop | ~6KB | Main USB async transfer loop |
| 0x67424 | sv_libusb_hid_init | 528B | USB device initialization |
| 0x67634 | Sys_HID_SendData | 692B | Send command via interrupt transfer |
| 0x687c8 | sv_hid_setHmdCmd | 460B | Command ID → packet length mapping |
| 0x6a7c4 | sv_hid_getHmdCmdData | 5292B | Send command + wait for response |
| 0x6bc70 | sv_hid_init | 148B | Top-level init (store FD) |
| 0x6bd04 | sv_hid_start | 464B | Start worker thread |

## 8. Implementation Strategy for Driver

### Minimum Viable IMU Reader

```
1. Open USB device (VID=0x2A45, PID=0x2050)
2. Claim interface 3 (or 4, try both)
3. Send IMU enable command (cmd 0x6d) to EP 0x03
4. Read 64-byte packets from EP 0x81 (and/or 0x83)
5. Filter for packets with byte[0]==0x42, byte[4]==0x01
6. Extract float32 values from bytes 8+ (candidate offsets)
7. Monitor for FRAME LOST via sequence counter
```

### What Needs Live Validation

1. **Exact raw byte offsets** for sensor values within the 64-byte packet
2. **Command buffer format** for cmd 0x6d (enable IMU) — what bytes to send
3. **Which USB interface** to claim (3 vs 4 vs both)
4. **Which IN endpoint** carries IMU data (0x81 vs 0x83 vs 0x85)
5. **IMU sample rate** and how to set it via cmd 0x20
6. **Coordinate system** (right-hand? which axis is up?)

### Validation Approach

Build a minimal USB sniffer that:
1. Enumerates all interfaces and endpoints
2. Claims interface 3, reads packets, identifies IMU data by 0x42 header
3. Hexdumps first 20 IMU packets for byte-level analysis
4. Tries sending cmd 0x6d buffer (all zeros + enable flag) to trigger IMU stream
