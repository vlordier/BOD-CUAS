# BOD-CUAS — Bordeaux Airport Counter-UAS Protection

## Overview

This repository documents the C-UAS (Counter-Unmanned Aircraft System) protection architecture for **Bordeaux-Mérignac Airport (ICAO: LFBD, IATA: BOD)**. It captures the relevant primitives, equations, models, and algorithms from the [furia-core](https://github.com/vlordier/furia-core) ecosystem that apply to protecting a civilian airport from drone threats.

**Airport:** Bordeaux-Mérignac Airport  
**Location:** 44°49′42″N, 0°42′56″W  
**Runways:** 05/23 (3,100 m), 11/29 (2,415 m)  
**Traffic:** ~6.5M passengers/year, military/civilian co-use (BA 106)  
**Airspace:** Class D CTR, 5 NM radius, surface to 2,500 ft AGL  

---

## 1. Airport Airspace Model

### 1.1 Zone Types

The following zone types from `furia-domain::domain::zone::ZoneType` are relevant for BOD:

| Zone Type | BOD Application | Altitude Band |
|-----------|----------------|---------------|
| `RunwayProtectionZone` | Trapezoidal area extending 300m × 150m from each runway threshold | Surface–150 ft AGL |
| `IlsCriticalArea` | ILS localizer (05/23) and glideslope critical areas | Surface–600 m |
| `ApproachDeparturePath` | 3D corridor along extended centerlines (05/23, 11/29) | Surface–3,000 ft |
| `ControlZone` | Class D CTR — 5 NM radius around BOD | Surface–2,500 ft AGL |
| `TerminalManeuveringArea` | BOD TMA — 20 NM radius | 1,500–6,000 ft |
| `FuelStorageZone` | Jet fuel depot at BA 106 | Surface–50 m |
| `PassengerTerminalZone` | Terminal buildings, apron areas | Surface–50 m |
| `AtcTowerZone` | ATC tower + 200 m radius | Surface–100 m |

### 1.2 Airport Subtype

```rust
AirportZoneSubtype::Bordeaux  // ICAO: LFBD, IATA: BOD
```

### 1.3 Flight Rule Activation

```rust
FlightRuleActivation::All      // Active under both VFR and IFR
FlightRuleActivation::VfrOnly  // Active only in VMC
FlightRuleActivation::IfrOnly  // Active only in IMC
```

For BOD, the ILS critical area and approach paths should use `IfrOnly` during low-visibility operations, while the CTR and RPZ should use `All`.

### 1.4 Zone Boundary Types

```rust
ZoneBoundary::Circle { center: Coord, radius_meters: f64 }
ZoneBoundary::Polygon { coordinates: Vec<Coord> }
ZoneBoundary::Corridor { start: Coord, end: Coord, width_meters: f64 }
```

---

## 2. Drone RF Detection

### 2.1 Frequency Bands

From `furia-ew::models::DroneFrequencyBand`:

| Band | Range | Common Protocols |
|------|-------|-----------------|
| `Band868Mhz` | 863–870 MHz | EU SRD band, some MAVLink telemetry |
| `Band915Mhz` | 902–928 MHz | US ISM, MAVLink, ExpressLRS |
| `Band2_4Ghz` | 2,400–2,483.5 MHz | DJI OcuSync, Wi-Fi, FrSky, FlySky |
| `Band5_8Ghz` | 5,725–5,850 MHz | DJI OcuSync 3.0 fallback, FPV |

### 2.2 Drone Protocol Fingerprinting

From `furia-ew::models::EmitterType`:

| Protocol | Type | Modulation | Bandwidth | Key Features |
|----------|------|------------|-----------|--------------|
| DJI OcuSync 1.0 | `DjiOcuSync` | OFDM QPSK | ~20 MHz | 2.4 GHz, proprietary hopping |
| DJI OcuSync 2.0 | `DjiOcuSync` | OFDM QPSK | ~20 MHz | 2.4 GHz, improved range |
| DJI OcuSync 3.0 | `DjiOcuSync` | OFDM QPSK | ~20 MHz | 2.4 + 5.8 GHz, 15 km range |
| MAVLink Telemetry | `MavlinkTelemetry` | GFSK | 100 kHz | 915/868 MHz, CRC-16/X.25 |
| ExpressLRS | `ExpressLrs` | LoRa FHSS | 125–1000 kHz | 915 MHz/2.4 GHz, open protocol |
| FrSky ACCST D16 | `FrSkyAccst` | GFSK | ~500 kHz | 2.4 GHz, D16 mode |
| FlySky AFHDS 2A | `FlySkyAfhds` | GFSK AFH | ~400 kHz | 2.4 GHz, 8-14 channels |
| ADS-B Drone | `AdsbDrone` | Pulse | 1 MHz | 1090 MHz, Mode S ES |
| Remote ID | `RemoteId` | BLE/Wi-Fi | 1–20 MHz | ASTM F3411 broadcast |

### 2.3 Drone Emitter Library

From `furia-ew::eob::EobStore::default_drone_library()` — 7 pre-configured entries:

1. **DJI Mavic 3 (OcuSync 3.0, 2.4 GHz)** — confidence 0.85
2. **DJI Mavic 3 (OcuSync 3.0, 5.8 GHz)** — confidence 0.80
3. **DJI Phantom 4 (OcuSync 1.0, 2.4 GHz)** — confidence 0.85
4. **MAVLink Telemetry (915 MHz)** — confidence 0.75
5. **ExpressLRS (2.4 GHz)** — confidence 0.70
6. **FrSky ACCST D16 (2.4 GHz)** — confidence 0.75
7. **ADS-B Drone Transponder (1090 MHz)** — confidence 0.90

### 2.4 Protocol Parameters

```rust
DroneProtocolParams::DjiOcuSync {
    generation: OcuSyncGeneration::OcuSync3,
    frequency_band: DroneFrequencyBand::Band2_4Ghz,
    bandwidth_mhz: 20.0,
    hopping_sequence_id: None,
}

DroneProtocolParams::MavlinkTelemetry {
    frequency_mhz: 915.0,
    baud_rate: 115200,
    system_id: Some(1),
    component_id: Some(1),
}

DroneProtocolParams::ExpressLrs {
    frequency_band: DroneFrequencyBand::Band2_4Ghz,
    spreading_factor: 6,      // 64 chips/symbol
    bandwidth_khz: 500,       // 500 kHz
    coding_rate: 4,           // 4/5
}
```

---

## 3. Micro-Doppler Analysis

### 3.1 Key Equations

**Blade flash period:**
$$T_{flash} = \frac{60}{N_b \cdot RPM}$$

**Blade passage frequency (BPF):**
$$f_{BPF} = \frac{N_b \cdot RPM}{60}$$

**Micro-Doppler bandwidth:**
$$\Delta f_{mD} = \frac{4\pi L_{blade} \cdot RPM}{\lambda \cdot 60}$$

**Flash-to-body ratio:**
$$R_{fb} = \frac{P_{flash}}{P_{body}}$$

### 3.2 Drone Micro-Doppler Templates

From `furia-signal-processing::micro_doppler::DRONE_MICRO_DOPPLER_TEMPLATES`:

| Drone | Blades | RPM | Blade Length | BPF | Flash Period | Δf (X-band) |
|-------|--------|-----|-------------|-----|-------------|-------------|
| DJI Mavic 3 | 2 | 6,000 | 0.15 m | 200 Hz | 5 ms | 6,283 Hz |
| DJI Phantom 4 | 2 | 5,000 | 0.12 m | 167 Hz | 6 ms | 4,189 Hz |
| DJI Inspire 2 | 2 | 4,500 | 0.18 m | 150 Hz | 6.7 ms | 5,655 Hz |
| Autel EVO II | 2 | 5,500 | 0.14 m | 183 Hz | 5.5 ms | 5,377 Hz |
| Skydio 2+ | 2 | 5,200 | 0.13 m | 173 Hz | 5.8 ms | 4,712 Hz |
| FPV 5-inch | 2 | 12,000 | 0.064 m | 400 Hz | 2.5 ms | 5,361 Hz |
| FPV 7-inch | 2 | 8,000 | 0.089 m | 267 Hz | 3.75 ms | 4,972 Hz |

### 3.3 Drone Confidence Scoring

```rust
fn compute_drone_confidence(
    fundamental_hz: f64,    // BPF or flash fundamental
    doppler_bw_hz: f64,     // Micro-Doppler bandwidth
    flash_to_body: f64,     // Flash-to-body power ratio
    harmonic_count: usize,  // Number of detectable harmonics
) -> f64
```

Scoring weights:
- **Fundamental frequency (30%)**: 50–500 Hz → drone, 20–50 Hz → possible, <20 Hz → unlikely
- **Doppler bandwidth (25%)**: 50–1000 Hz → drone, 10–50 Hz → possible, <10 Hz → bird/aircraft
- **Flash-to-body ratio (25%)**: ≥3.0 → drone, ≥1.5 → possible, <1.5 → bird
- **Harmonic count (20%)**: ≥3 → drone, ≥2 → possible, <2 → bird/aircraft

---

## 4. Cyclostationary / OFDM Detection

### 4.1 Key Equations

**Cyclic autocorrelation function (CAF):**
$$R_x^\alpha(\tau) = \sum_{n=0}^{N-1-|\tau|} x[n+\tau] \cdot x^*[n] \cdot e^{-j2\pi\alpha n/f_s}$$

**Spectral correlation density (SCD):**
$$S_x^\alpha(f) = \int_{-\infty}^{\infty} R_x^\alpha(\tau) \cdot e^{-j2\pi f\tau} d\tau$$

### 4.2 OFDM Protocol Templates

From `furia-signal-processing::cyclostationary::DRONE_OFDM_TEMPLATES`:

| Protocol | Symbol Rate | CP Fraction | Subcarrier Spacing | Subcarriers | Bandwidth |
|----------|------------|-------------|-------------------|-------------|-----------|
| DJI OcuSync 1.0 | 15 kHz | 0.125 | 15 kHz | 52 | 20 MHz |
| DJI OcuSync 2.0 | 20 kHz | 0.10 | 20 kHz | 64 | 20 MHz |
| DJI OcuSync 3.0 | 25 kHz | 0.08 | 25 kHz | 128 | 20 MHz |
| Wi-Fi 802.11n | 40 kHz | 0.25 | 312.5 kHz | 52 | 20 MHz |

### 4.3 Detection Pipeline

1. Compute CAF across a range of cyclic frequencies $\alpha$
2. Detect peaks at $\alpha = 1/T_{sym}$ (symbol rate) and $\alpha = 1/T_{cp}$ (cyclic prefix)
3. Check harmonic structure for subcarrier spacing
4. Match against known OFDM templates
5. Return best-matching protocol + confidence

---

## 5. Civilian Aircraft Fratricide Protection

### 5.1 Fratricide Outcome Types

```rust
enum FratricideOutcome {
    Clear,                                    // Safe to engage
    CivilianAirliner {                        // ALWAYS BLOCKED
        flight_id: String,
        icao_code: String,
        distance_km: f64,
        phase: String,                        // "approach", "departure", "cruise", "taxi"
    },
    AirportProtectedZone {                    // BLOCKED in protected zones
        zone_type: String,
        zone_name: String,
        airport_icao: String,
    },
    FriendlyProximity { ... },                // Friendly forces too close
    IffFriendly { ... },                      // IFF identifies as friendly
    GeofenceViolation { ... },               // Inside no-fratricide zone
    BftUnavailable,                           // No BFT data — fail closed
    BftStale { ... },                         // BFT data too old
}
```

### 5.2 Airport-Specific Rules

From `furia-domain::fratricide::FratricideCheck::check_civilian_aircraft()`:

| Condition | Action | Rationale |
|-----------|--------|-----------|
| Civilian aircraft on approach within 10 km of airport | **BLOCK** | Highest risk — aircraft on final approach |
| Civilian aircraft on departure within 10 km of airport | **BLOCK** | Aircraft climbing out, limited maneuverability |
| Any civilian aircraft within 3 km of airport | **BLOCK** | Taxi, ground ops, low-altitude overflight |
| Target in ILS critical area | **BLOCK** | Must not disrupt precision approach |
| Target in runway protection zone | **BLOCK** | Direct collision risk with landing/taking-off aircraft |
| Target in fuel storage zone | **BLOCK** | Catastrophic fire/explosion risk |

---

## 6. C-UAS Targeting

### 6.1 Target Types

From `furia-targeting::models::TargetType`:

| Type | Description | Typical Engagement |
|------|-------------|-------------------|
| `Uas` | Single unmanned aerial system | Kinetic interceptor, RF jammer |
| `UasSwarm` | Multiple UAS operating cooperatively | DEW (laser), wide-area jammer |
| `LoiteringMunition` | One-way attack drone | Kinetic interceptor |
| `UasGroundControlStation` | GCS for UAS operations | Kinetic (if permissible) |

### 6.2 Weapon Types

From `furia-lethality::hit_probability::WeaponType`:

| Type | Description | Dispersion | Effective Range |
|------|-------------|------------|-----------------|
| `KineticInterceptor` | AHEAD, 30mm proximity-fuzed | 0.1 mil | 500–3,000 m |
| `RfJammer` | Soft-kill RF jammer | 5.0 mil (beamwidth) | 500–5,000 m |
| `DirectedEnergy` | Laser, HPM | 0.05 mil (diffraction-limited) | 500–2,000 m |
| `NetCapture` | Net/grid capture system | 10.0 mil | 50–300 m |

---

## 7. Threat Scoring (WASM Module)

### 7.1 Scoring Factors

From `examples/wasm-threat-scorer/src/lib.rs`:

| Factor | Weight | Description |
|--------|--------|-------------|
| Speed | 20% | Higher speed → higher threat (saturates at 500 m/s) |
| Altitude | 20% | Lower altitude → higher threat (inverse linear, saturates at 5,000 m) |
| Group size | 15% | More entities → higher threat (saturates at 10) |
| Heading | 25% | Heading toward airport → higher threat |
| Proximity | 20% | Closer to airport → higher threat (saturates at 10 km) |

### 7.2 Threat Levels

| Score | Level | Action |
|-------|-------|--------|
| ≥ 0.70 | **HIGH** | Immediate engagement, all abort rules checked |
| ≥ 0.40 | **MEDIUM** | Monitor, prepare engagement, cue sensors |
| < 0.40 | **LOW** | Log and track only |

---

## 8. Bordeaux Airport-Specific Configuration

### 8.1 Runway Geometry

| Runway | Heading | Length | ILS | RPZ Dimensions |
|--------|---------|--------|-----|----------------|
| 05/23 | 046° / 226° | 3,100 m | Cat I (05) | 900m × 300m (each end) |
| 11/29 | 114° / 294° | 2,415 m | None | 750m × 300m (each end) |

### 8.2 Airspace Structure

```
BOD CTR:     5 NM radius, centered on 44°49′42″N 0°42′56″W, SFC–2,500 ft AGL
BOD TMA:     20 NM radius, 1,500–6,000 ft
Approach 05: 046° radial, 3° glideslope, intercept at 2,000 ft, 8 NM final
Approach 23: 226° radial, 3° glideslope, intercept at 2,000 ft, 8 NM final
Departure 05: 046° radial, climb to 3,000 ft before turn
Departure 23: 226° radial, climb to 3,000 ft before turn
```

### 8.3 Threat Zones (Priority Order)

1. **ILS Critical Area (Runway 05)** — Highest priority, never engage
2. **Runway Protection Zones** — Never engage when aircraft on approach/departure
3. **Approach/Departure Corridors** — Never engage when civilian aircraft present
4. **Fuel Storage (BA 106)** — Never engage
5. **Passenger Terminal** — Never engage
6. **ATC Tower** — Never engage
7. **CTR Boundary** — Engage only with ATC coordination
8. **TMA** — Monitor, engage only if heading toward airport

### 8.4 Sensor Placement

| Sensor Type | Location | Coverage |
|-------------|----------|----------|
| RF Scanner (2.4/5.8 GHz) | Terminal roof | 360°, 5 km range |
| RF Scanner (868/915 MHz) | BA 106 tower | 360°, 3 km range |
| Acoustic Array | Approach end RWY 05 | 120° sector, 1 km range |
| Acoustic Array | Approach end RWY 23 | 120° sector, 1 km range |
| EO/IR Camera | ATC Tower | 360°, pan/tilt/zoom |
| Micro-Doppler Radar (X-band) | Near threshold RWY 05 | 90° sector, 3 km range |
| Micro-Doppler Radar (X-band) | Near threshold RWY 23 | 90° sector, 3 km range |

---

## 9. Key Equations Reference

### 9.1 RF Detection

**Free-space path loss:**
$$L_{fs} = 20 \log_{10}(d) + 20 \log_{10}(f) + 32.44$$

**Received signal power:**
$$P_r = P_t + G_t + G_r - L_{fs} - L_{atm}$$

### 9.2 Acoustic Detection

**Sound pressure level from drone:**
$$SPL = 60 + 20 \log_{10}(N_{blades}) + 50 \log_{10}(RPM/1000) - 20 \log_{10}(d) - \alpha d$$

**Blade passage frequency:**
$$f_{BPF} = \frac{N_b \cdot RPM}{60}$$

### 9.3 Radar Detection

**Micro-Doppler bandwidth:**
$$\Delta f_{mD} = \frac{4\pi L_{blade} \cdot RPM}{\lambda \cdot 60}$$

**Radar range equation:**
$$R_{max} = \left[ \frac{P_t G^2 \lambda^2 \sigma}{(4\pi)^3 k T B F L} \right]^{1/4}$$

### 9.4 Sensor Fusion

**Haversine distance:**
$$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta lat}{2}\right) + \cos(lat_1)\cos(lat_2)\sin^2\left(\frac{\Delta lon}{2}\right)}\right)$$

**Weighted fusion confidence:**
$$C_{fused} = \frac{\sum_i w_i C_i}{\sum_i w_i}$$

### 9.5 Cyclostationary Detection

**Cyclic autocorrelation:**
$$R_x^\alpha(\tau) = \sum_{n=0}^{N-1-|\tau|} x[n+\tau] \cdot x^*[n] \cdot e^{-j2\pi\alpha n/f_s}$$

**OFDM symbol rate detection:**
$$\hat{\alpha}_{sym} = \arg\max_\alpha |R_x^\alpha(\tau)| \quad \text{for } \tau = T_{sym}$$

---

## 11. Multi-Modal Sensor Fusion

### 11.1 Architecture

From `furia-sensor-fusion::multi_modal_fusion` — orchestrates fusion across 5 sensor modalities:

| Modality | Position Weight | Velocity Weight | Classification Confidence |
|----------|----------------|-----------------|--------------------------|
| Radar | 0.40 | 0.35 | 0.50 (default) |
| RF Scanner | 0.25 | 0.25 | 0.70 (RF detection) |
| Acoustic Array | 0.15 | 0.10 | 0.40 (default) |
| EO/IR Camera | 0.20 | 0.30 | 0.60 (visual classification) |
| Micro-Doppler Radar | 0.40 | 0.35 | 0.75 (micro-Doppler) |

### 11.2 Fusion Pipeline

1. **Time alignment** — Interpolates measurements to median timestamp within configurable window (default 50ms)
2. **Covariance intersection** — Fuses state estimates across modalities using CI formula
3. **Classification fusion** — Weighted voting across modalities for drone type identification
4. **Track quality** — Computed from modality count, recency, and covariance trace

### 11.3 Fusion Equation

$$P_{fused}^{-1} = \omega \cdot P_1^{-1} + (1-\omega) \cdot P_2^{-1}$$

$$C_{fused} = \frac{\sum_i w_i \cdot c_i}{\sum_i w_i}$$

---

## 12. CBBA Consensus Phase

### 12.1 Algorithm

From `furia-task-allocation::consensus_phase` — implements the full Consensus-Based Bundle Algorithm:

1. **Bundle building** — Each agent greedily selects tasks by descending score
2. **Bundle sharing** — Agents share bundles with neighbors (adjacency matrix)
3. **Conflict resolution** — For each task, higher bid wins; equal bids broken by timestamp then agent index
4. **Convergence detection** — Algorithm converges when all agent scores change below threshold

### 12.2 Consensus Rules

| Condition | Winner |
|-----------|--------|
| Higher bid | Higher bid wins |
| Equal bid, different timestamp | More recent timestamp wins |
| Equal bid, equal timestamp | Lower agent index wins |

---

## 13. BOIDS Swarm Algorithm

### 13.1 Forces

From `furia-formation-physics::boids` — Craig Reynolds' BOIDS algorithm:

| Force | Weight | Description |
|-------|--------|-------------|
| Separation | 1.5 | Steer away from nearby boids (inverse distance, 25m radius) |
| Alignment | 1.0 | Steer toward average heading of neighbors (100m radius) |
| Cohesion | 1.0 | Steer toward center of mass of neighbors (100m radius) |
| Goal-seeking | 0.5 | Steer toward mission goal position |

### 13.2 Update Loop

$$\vec{F} = w_s \cdot \vec{S} + w_a \cdot \vec{A} + w_c \cdot \vec{C} + w_g \cdot \vec{G}$$

$$\vec{v}_{t+1} = \vec{v}_t + \frac{\vec{F}}{m} \cdot \Delta t$$

$$\vec{p}_{t+1} = \vec{p}_t + \vec{v}_{t+1} \cdot \Delta t$$

---

## 14. Bidirectional MAVLink Adapter

### 14.1 Commands

From `adapters/mavlink-adapter::command`:

| Command | MAV_CMD | Parameters |
|---------|---------|------------|
| Arm | 400 (ARM_DISARM) | param1=1.0 |
| Disarm | 400 (ARM_DISARM) | param1=0.0 |
| Takeoff | 22 (NAV_TAKEOFF) | param7=altitude_m |
| Land | 21 (NAV_LAND) | — |
| RTL | 20 (NAV_RETURN_TO_LAUNCH) | — |
| Guided Goto | 51 (DO_REPOSITION) | param5=lat, param6=lon, param7=alt |
| Set Mode | 176 (DO_SET_MODE) | param1=mode_number |
| Set Speed | 178 (DO_CHANGE_SPEED) | param1=speed_mps, param2=-1 |
| Mission Start | 300 (MISSION_START) | — |
| Mission Pause | 197 (DO_PAUSE_CONTINUE) | param1=0.0 |

### 14.2 Heartbeat

HEARTBEAT (msg_id=0) with MAV_TYPE_QUADROTOR (2), MAV_AUTOPILOT_ARDUPILOTMEGA (8), base_mode 81, MAV_STATE_ACTIVE (4).

---

## 15. Geofence Enforcement Engine

### 15.1 Fence Types

From `furia-airspace::geofence`:

| Type | Geometry | BOD Application |
|------|----------|-----------------|
| Circular | Center + radius_m | CTR (5 NM), TMA (20 NM) |
| Polygonal | Vertex list | Terminal area, BA 106 fuel depot |
| AltitudeBand | min_m, max_m | Altitude envelope (SFC–2,500 ft) |
| Cylindrical | Center + radius + altitude | ILS critical area, approach corridors |
| RunwayExclusion | Start/end + half_width | Runway 05/23 and 11/29 exclusion zones |

### 15.2 Enforcement Actions

| Severity | Action | Use Case |
|----------|--------|----------|
| 0 | None | Monitoring only |
| 1 | Warning | Approaching boundary |
| 2 | SpeedLimit | Near protected zone |
| 3 | AltitudeCap | Altitude violation |
| 4 | ReturnToLaunch | Runway incursion |
| 5 | LandImmediately | Critical zone violation |

### 15.3 Breach Prediction

Projects position along velocity vector and checks for future violations within configurable time horizon.

---

## 16. CBF Safety Shield

### 16.1 CBF Types

From `furia-collision-avoidance::control_barrier_function`:

| CBF | $h(x)$ | Application |
|-----|--------|-------------|
| Separation | $\|p_i - p_j\| - d_{min}$ | Interceptor separation |
| Geofence | $R - \|p - p_{center}\|$ | Stay inside boundary |
| Altitude | $z - z_{min}$, $z_{max} - z$ | Altitude envelope |
| Runway | $\|p - p_{rwy}\| - d_{rwy}$ | Runway exclusion |
| Speed | $v_{max} - \|v\|$ | Maximum speed |

### 16.2 QP Safety Filter

$$\min_{u \in \mathbb{R}^3} \frac{1}{2}\|u - u_{nom}\|^2$$
$$\text{s.t. } L_f h_i + L_g h_i \cdot u + \alpha_i \cdot h_i \geq 0, \quad \forall i$$

---

## 17. ORCA Multi-Agent Avoidance

### 17.1 Half-Plane Constraints

From `furia-collision-avoidance::optimal_reciprocal_collision_avoidance`:

$$ORCA_{i|j} = \{v \mid (v - (v_i^{opt} + v_j^{opt})/2) \cdot n \geq 0\}$$

### 17.2 Solver

Linear programming in 2D: finds closest velocity to preferred velocity within intersection of all ORCA half-planes and max speed constraint.

---

## 18. Intercept Guidance

### 18.1 Guidance Laws

From `furia-intercept-guidance`:

| Law | Equation | Use Case |
|-----|----------|----------|
| PN | $a_c = N \cdot v_c \cdot \dot{\lambda}$ | Standard intercept |
| APN | $a_c = N \cdot v_c \cdot \dot{\lambda} + \frac{N}{2} \cdot a_T$ | Evading targets |
| Pure Pursuit | $a_c = k \cdot (\psi_T - \psi_I)$ | Short-range intercept |

### 18.2 Intercept Point

Solves quadratic for simultaneous arrival: $\|p_T + v_T \cdot t - p_I\| = v_I \cdot t$

---

## 19. Source Files Reference

| File | Content |
|------|---------|
| `furia-domain/src/domain/zone.rs` | Airport zone types, subtypes, flight rules |
| `furia-domain/src/fratricide.rs` | Civilian aircraft fratricide protection |
| `furia-ew/src/models.rs` | Drone RF protocol types, frequency bands |
| `furia-ew/src/eob.rs` | Drone emitter library, TDOA geolocation |
| `furia-ew/src/es.rs` | ES task manager, intercept correlation |
| `furia-ew/src/ea.rs` | EA planning, DEW engagement |
| `furia-signal-processing/src/micro_doppler.rs` | Micro-Doppler analysis module |
| `furia-signal-processing/src/cyclostationary.rs` | OFDM/cyclostationary detection |
| `furia-signal-processing/src/filters.rs` | IIR/FIR filters, FFT |
| `furia-signal-processing/src/detection_theory.rs` | CFAR, matched filter |
| `furia-signal-processing/src/spectral_analysis.rs` | Spectrogram, PSD, Doppler |
| `furia-signal-processing/src/beamforming.rs` | MVDR, MUSIC, delay-and-sum |
| `furia-targeting/src/models.rs` | C-UAS target types |
| `furia-lethality/src/hit_probability.rs` | C-UAS weapon types, dispersion |
| `furia-airspace/src/corridor.rs` | Transit corridor management |
| `furia-airspace/src/deconfliction.rs` | Airspace deconfliction |
| `furia-cop/src/sensor_fusion.rs` | Multi-sensor fusion engine |
| `furia-iff/src/models.rs` | IFF, affiliation resolution |
| `furia-iff/src/interrogation.rs` | IFF interrogation scheduler |
| `furia-acoustics/src/uav_detection.rs` | Acoustic drone detection |
| `furia-acoustics/src/sound_ranging.rs` | TDOA acoustic localization |
| `furia-acoustics/src/noise_propagation.rs` | Noise propagation models |
| `examples/wasm-threat-scorer/src/lib.rs` | WASM threat scoring module |
| `services/counter-uas-director/src/abort_rules.rs` | Engagement abort rules |
| `services/counter-uas-director/src/fsm/` | F2T2EA kill-chain FSM |
| `services/counter-uas-director/src/physics_engine.rs` | Engagement physics |
| `furia-sensor-fusion/src/multi_modal_fusion.rs` | Multi-modal fusion orchestrator (NEW) |
| `furia-task-allocation/src/consensus_phase.rs` | Full CBBA consensus phase (NEW) |
| `furia-formation-physics/src/boids.rs` | BOIDS swarm algorithm (NEW) |
| `adapters/mavlink-adapter/src/command.rs` | Bidirectional MAVLink commands (NEW) |
| `furia-airspace/src/geofence.rs` | Geofence enforcement engine (NEW) |
| `furia-collision-avoidance/src/control_barrier_function.rs` | CBF safety shield (NEW) |
| `furia-collision-avoidance/src/optimal_reciprocal_collision_avoidance.rs` | ORCA multi-agent avoidance (NEW) |
| `furia-intercept-guidance/src/lib.rs` | Intercept guidance PN/APN/pursuit (NEW) |