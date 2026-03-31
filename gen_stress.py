"""Generate stress_devices.yaml — 50 Modbus TCP devices, 10 registers each.

Five device profiles × 10 devices each. Ports 16000–16049.
Run: python gen_stress.py
"""

import yaml

BASE_PORT = 16000
COUNT = 50

PROFILES = [
    # ── pump ─────────────────────────────────────────────────────────────────
    {
        "sim_tick": 1,
        "registers": [
            {
                "id": "temperature", "reg_type": "holding",
                "address": 0, "reg_size": 2, "format": "float", "test_value": 253.0,
                "sim": {"type": "sine", "min": 200.0, "max": 320.0, "period": 60},
            },
            {
                "id": "rpm", "reg_type": "holding",
                "address": 2, "format": "uint", "test_value": 1500,
                "sim": {"type": "ramp", "min": 800, "max": 2200, "period": 30},
            },
            {
                "id": "pressure", "reg_type": "holding",
                "address": 3, "reg_size": 2, "format": "float", "test_value": 1013.0,
            },
            {
                "id": "flow_rate", "reg_type": "holding",
                "address": 5, "format": "uint", "test_value": 120,
            },
            {
                "id": "setpoint", "reg_type": "holding",
                "address": 6, "format": "int", "test_value": 200, "writeable": True,
            },
            {"id": "running",  "reg_type": "coil",     "address": 0, "test_value": 1, "writeable": True},
            {"id": "enable",   "reg_type": "coil",     "address": 1, "test_value": 1, "writeable": True},
            {"id": "fault",    "reg_type": "discrete", "address": 0, "test_value": 0},
            {"id": "alarm",    "reg_type": "discrete", "address": 1, "test_value": 0},
            {
                "id": "load_pct", "reg_type": "input",
                "address": 0, "format": "uint", "test_value": 75,
                "sim": {"type": "sine", "min": 30, "max": 95, "period": 45},
            },
        ],
    },
    # ── tank ──────────────────────────────────────────────────────────────────
    {
        "sim_tick": 2,
        "registers": [
            {
                "id": "level", "reg_type": "holding",
                "address": 0, "reg_size": 2, "format": "float", "test_value": 50.0,
                "sim": {"type": "ramp", "min": 10.0, "max": 90.0, "period": 120},
            },
            {
                "id": "temperature", "reg_type": "holding",
                "address": 2, "format": "uint", "test_value": 250,
            },
            {"id": "inlet_flow",   "reg_type": "holding", "address": 3, "format": "uint", "test_value": 80},
            {"id": "outlet_flow",  "reg_type": "holding", "address": 4, "format": "uint", "test_value": 60},
            {
                "id": "vol_setpoint", "reg_type": "holding",
                "address": 5, "format": "uint", "test_value": 800, "writeable": True,
            },
            {"id": "valve1_open", "reg_type": "coil",     "address": 0, "test_value": 1, "writeable": True},
            {"id": "valve2_open", "reg_type": "coil",     "address": 1, "test_value": 0, "writeable": True},
            {"id": "overflow",    "reg_type": "discrete", "address": 0, "test_value": 0},
            {"id": "empty",       "reg_type": "discrete", "address": 1, "test_value": 0},
            {"id": "density",     "reg_type": "input",    "address": 0, "format": "uint", "test_value": 998},
        ],
    },
    # ── motor ─────────────────────────────────────────────────────────────────
    {
        "sim_tick": 1,
        "registers": [
            {
                "id": "speed", "reg_type": "holding",
                "address": 0, "reg_size": 2, "format": "float", "test_value": 1450.0,
                "sim": {"type": "sine", "min": 1200.0, "max": 1500.0, "period": 20},
            },
            {
                "id": "torque", "reg_type": "holding",
                "address": 2, "reg_size": 2, "format": "float", "test_value": 95.5,
            },
            {"id": "current",        "reg_type": "holding", "address": 4, "format": "uint", "test_value": 150},
            {"id": "voltage",        "reg_type": "holding", "address": 5, "format": "uint", "test_value": 2300},
            {
                "id": "speed_setpoint", "reg_type": "holding",
                "address": 6, "format": "uint", "test_value": 1450, "writeable": True,
            },
            {"id": "enable",   "reg_type": "coil",     "address": 0, "test_value": 1, "writeable": True},
            {"id": "fault",    "reg_type": "discrete", "address": 0, "test_value": 0},
            {"id": "ready",    "reg_type": "discrete", "address": 1, "test_value": 1},
            {"id": "power_kw", "reg_type": "input",    "address": 0, "format": "uint", "test_value": 34},
            {"id": "runtime_h","reg_type": "input",    "address": 1, "format": "uint", "test_value": 2500},
        ],
    },
    # ── conveyor ──────────────────────────────────────────────────────────────
    {
        "sim_tick": 2,
        "registers": [
            {
                "id": "belt_speed", "reg_type": "holding",
                "address": 0, "format": "uint", "test_value": 150,
                "sim": {"type": "ramp", "min": 0, "max": 200, "period": 60},
            },
            {
                "id": "position", "reg_type": "holding",
                "address": 1, "reg_size": 2, "format": "float", "test_value": 0.0,
            },
            {"id": "load_kg",      "reg_type": "holding", "address": 3, "format": "uint", "test_value": 500},
            {"id": "tension",      "reg_type": "holding", "address": 4, "format": "uint", "test_value": 800},
            {
                "id": "spd_setpoint", "reg_type": "holding",
                "address": 5, "format": "uint", "test_value": 150, "writeable": True,
            },
            {"id": "running",     "reg_type": "coil",     "address": 0, "test_value": 0, "writeable": True},
            {"id": "direction",   "reg_type": "coil",     "address": 1, "test_value": 1, "writeable": True},
            {"id": "jam_detected","reg_type": "discrete", "address": 0, "test_value": 0},
            {"id": "limit_switch","reg_type": "discrete", "address": 1, "test_value": 0},
            {"id": "total_cycles","reg_type": "input",    "address": 0, "format": "uint", "test_value": 15000},
        ],
    },
    # ── sensor_hub ────────────────────────────────────────────────────────────
    {
        "sim_tick": 5,
        "registers": [
            {
                "id": "temp1", "reg_type": "holding",
                "address": 0, "reg_size": 2, "format": "float", "test_value": 215.0,
                "sim": {"type": "sine", "min": 180.0, "max": 280.0, "period": 90},
            },
            {
                "id": "temp2", "reg_type": "holding",
                "address": 2, "reg_size": 2, "format": "float", "test_value": 220.0,
                "sim": {"type": "sine", "min": 190.0, "max": 270.0, "period": 75, "phase": 20},
            },
            {"id": "humidity",    "reg_type": "holding", "address": 4, "format": "uint", "test_value": 650},
            {"id": "pressure",    "reg_type": "holding", "address": 5, "format": "uint", "test_value": 1013},
            {"id": "co2_ppm",     "reg_type": "holding", "address": 6, "format": "uint", "test_value": 450},
            {"id": "heater",      "reg_type": "coil",     "address": 0, "test_value": 0, "writeable": True},
            {"id": "fan",         "reg_type": "coil",     "address": 1, "test_value": 1, "writeable": True},
            {"id": "alarm",       "reg_type": "discrete", "address": 0, "test_value": 0},
            {"id": "battery_pct", "reg_type": "input",    "address": 0, "format": "uint", "test_value": 85},
            {"id": "rssi",        "reg_type": "input",    "address": 1, "format": "uint", "test_value": 72},
        ],
    },
]

PROFILE_NAMES = ["pump", "tank", "motor", "conveyor", "sensor_hub"]


def main() -> None:
    output = {}
    for i in range(COUNT):
        profile = PROFILES[i % len(PROFILES)]
        name = f"stress_{PROFILE_NAMES[i % len(PROFILES)]}_{i // len(PROFILES) + 1:02d}"
        output[name] = {
            "port_type": "modbus tcp",
            "ip": "127.0.0.1",
            "port": BASE_PORT + i,
            "slave_id": i + 1,
            "poll_time": 1,
            "sim_tick": profile["sim_tick"],
            "registers": profile["registers"],
        }

    with open("stress_devices.yaml", "w") as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    last_port = BASE_PORT + len(output) - 1
    print(f"stress_devices.yaml: {len(output)} devices, ports {BASE_PORT}–{last_port}")


if __name__ == "__main__":
    main()
