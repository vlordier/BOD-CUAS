# S1 ↔ furia-core Integration Bridge

## Purpose

This document maps the C-UAS airport protection primitives from `furia-core` into the S1 (Swarm Layer 1) verified runtime. S1 provides the **verified execution environment** (Kani, TLA+, no_std, no float, no panic), while furia-core provides the **domain models and algorithms** (airport zones, drone RF fingerprints, micro-Doppler, cyclostationary detection, CBF, ORCA, intercept guidance, multi-modal fusion, CBBA consensus, geofence enforcement, MAVLink commands).

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      furia-core                              │
│  (Domain models, algorithms, C-UAS primitives)               │
│                                                              │
│  Airport zones │ Drone RF │ Micro-Doppler │ Cyclostationary │
│  CBF │ ORCA │ Intercept Guidance │ Multi-modal Fusion       │
│  CBBA Consensus │ Geofence Enforcement │ MAVLink Commands   │
└──────────────────────┬──────────────────────────────────────┘
                       │  furia-bridge feature gate
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      S1 (Swarm Layer 1)                      │
│  (Verified runtime: Kani, TLA+, no_std, no float, no panic) │
│                                                              │
│  Guidance │ Formation │ ORCA3D │ Geofence │ Sensor Fusion   │
│  Task Allocation │ MAVLink │ Safety │ EMStop │ Deconfliction│
└─────────────────────────────────────────────────────────────┘
```

## Integration Points

### 1. Geofence → S1 Geofence

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-airspace::geofence::GeofenceType` (Circular, Polygonal, AltitudeBand, Cylindrical, RunwayExclusion) | `s1::geofence::FenceDefinition` (simple radius+altitude) | S1's geofence is a simplified cylindrical model. For airport protection, S1 should import furia-core's `GeofenceType` for the `consensus_fence::SharedFence` and use furia-core's `check_position()` for polygon/runway checks. |
| `furia-airspace::geofence::GeofenceEngine` (violation detection, breach prediction, enforcement actions) | `s1::geofence::check_position()` (simple altitude+radius) | S1's `push_to_obstacle_grid()` should accept furia-core `GeofenceType::RunwayExclusion` and `GeofenceType::Polygonal` to mark NoFly cells. |
| `furia-airspace::geofence::GeofenceAction` (Warning, AltitudeCap, SpeedLimit, RTL, LandImmediately) | `s1::coordination::RtlTriggerSource::GeofenceBreach` | S1's RTL trigger should map furia-core's `GeofenceAction::ReturnToLaunch` and `GeofenceAction::LandImmediately` to the appropriate S1 failsafe triggers. |

### 2. CBF → S1 Safety / Barrier

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-collision-avoidance::control_barrier_function::CbfSafetyFilter` (QP-based safety filter with separation, geofence, altitude, runway, speed CBFs) | `s1::barrier` (barrier certificates) | S1's barrier module should import furia-core's CBF types for runway exclusion and geofence enforcement. The `CbfFilterResult` can be used as an additional safety gate in `s1::safety::safety_gate()`. |
| `runway_exclusion_cbf()` | None | NEW: S1 should add a runway exclusion barrier certificate using furia-core's `runway_exclusion_cbf()` function, parameterized with BOD runway geometry (05/23: 046°/226°, 11/29: 114°/294°). |

### 3. ORCA → S1 ORCA3D

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-collision-avoidance::optimal_reciprocal_collision_avoidance::OrcaSolver` (2D ORCA with half-plane LP) | `s1::orca3d` (3D ORCA with velocity obstacles) | S1's ORCA3D is more advanced (3D). furia-core's ORCA is 2D. No integration needed — S1's implementation is superior. However, furia-core's `VelocityObstacle` and `ReciprocalVelocityObstacle` types can be used as reference models for S1's test harnesses. |

### 4. Intercept Guidance → S1 Guidance

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-intercept-guidance::InterceptGuidance` (PN, APN, pure pursuit, intercept point computation) | `s1::guidance` (formation slot tracking, waypoint following, trajectory smoothing) | S1's guidance module handles formation-hold and waypoint tracking. furia-core's intercept guidance is for **kinetic interceptors** (C-UAS effectors). These are complementary: S1 guides the interceptor drone to the intercept point computed by furia-core. |
| `compute_intercept_point()` | `s1::guidance::commands::GuidanceCommand` | The intercept point from furia-core should be converted to an S1 `GuidanceCommand` (waypoint or velocity command) via the `furia_bridge`. |

### 5. Multi-Modal Fusion → S1 Sensor Fusion

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-sensor-fusion::multi_modal_fusion::MultiModalFusionEngine` (5 modalities: Radar, RF, Acoustic, EO/IR, Micro-Doppler) | `s1::sensor_fusion::SensorFusionManager` (GPS, IMU, Barometer, Magnetometer, OpticalFlow, Camera, ULD) | S1's sensor fusion is for **navigation** (where am I?). furia-core's multi-modal fusion is for **target detection** (what's out there?). These are complementary. The `furia_bridge` should pass furia-core's `FusedMultiModalTrack` into S1's world model. |
| `FusedMultiModalTrack` | `s1::world_model` | Fused tracks from furia-core should be ingested into S1's world model as `Track` entries with classification confidence. |

### 6. CBBA Consensus → S1 Task Allocation

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-task-allocation::consensus_phase::cbba_full_allocation()` (full CBBA: bundle building + consensus phase with bid/timestamp/index tiebreaking) | `s1::task_allocation` (market-based: lowest-cost bid wins) | S1's task allocation is simpler (market-based bidding). furia-core's CBBA is more sophisticated (consensus-based with conflict resolution). For the Bordeaux C-UAS scenario, furia-core's CBBA should be used for **effector-to-target assignment** (which interceptor handles which drone), while S1's task allocation handles **mission tasking** (waypoints, recon, delivery). |
| `resolve_conflicts()` | `s1::task_allocation::Task::assign()` | S1's `assign()` picks lowest-cost bid. furia-core's `resolve_conflicts()` handles the case where multiple agents bid on the same task. For C-UAS, the CBBA consensus phase ensures no two interceptors target the same drone. |

### 7. MAVLink Commands → S1 MAVLink Adapter

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `adapters/mavlink-adapter::command::MavlinkCommandEncoder` (Arm, Disarm, Takeoff, Land, RTL, GuidedGoto, SetMode, SetSpeed, MissionStart, MissionPause) | `s1::mavlink_adapter` (stub: GuidanceCommand → SET_POSITION_TARGET_LOCAL_NED) | S1's MAVLink adapter is a minimal stub. furia-core's `MavlinkCommandEncoder` provides the full command set needed for C-UAS operations. S1 should use furia-core's encoder for: (1) Arming interceptors, (2) Sending guided-goto commands to the intercept point, (3) Initiating RTL after engagement. |
| `MavlinkHeartbeat::encode_heartbeat()` | None | S1 should periodically emit heartbeats using furia-core's encoder for GCS situational awareness. |
| `MavlinkMissionEncoder::encode_mission()` | None | For uploading patrol patterns to interceptors. |

### 8. Airport Abort Rules → S1 Safety / EMStop

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `counter-uas-director::abort_rules::AbortRuleEngine` (13 rules including 7 airport-specific) | `s1::safety::safety_gate()` (pre-arm checks), `s1::emstop` (emergency stop state machine) | S1's safety gate and EMStop should incorporate furia-core's airport abort rules. The `AbortContext` fields (civilian_aircraft_on_approach, in_ils_critical_area, crosses_active_runway, etc.) should be populated from S1's world model and checked before engagement. |
| `CivilianAircraftOnApproach` (severity 5) | `s1::emstop::Trigger::GeofenceBreach` | Map to EMStop trigger for immediate abort. |
| `IlsCriticalAreaIncursion` (severity 5) | `s1::emstop::Trigger::GeofenceBreach` | Map to EMStop trigger. |
| `RunwayCrossing` (severity 5) | `s1::emstop::Trigger::GeofenceBreach` | Map to EMStop trigger. |

### 9. Airport Zone Types → S1 Geofence / World Model

| furia-core | S1 | Integration |
|-----------|-----|-------------|
| `furia-domain::domain::zone::ZoneType` (RunwayProtectionZone, IlsCriticalArea, ApproachDeparturePath, ControlZone, TMA, FuelStorageZone, PassengerTerminalZone, AtcTowerZone) | `s1::geofence::FenceDefinition` (simple cylinder) | S1's `FenceDefinition` should be extended to support furia-core's zone types. The `consensus_fence::SharedFence` should carry a `zone_type` discriminator. |
| `AirportZoneSubtype::Bordeaux` | None | S1 should define BOD-specific geofence presets using furia-core's airport geometry. |

## Implementation Plan

### Phase 1: Documentation & Type Mapping (this document)
- [x] Map all integration points
- [ ] Create type conversion functions in `s1::furia_bridge`

### Phase 2: Geofence Integration
- [ ] Extend S1 `FenceDefinition` to support `GeofenceType::RunwayExclusion`
- [ ] Extend S1 `push_to_obstacle_grid()` to handle polygon and runway fences
- [ ] Add BOD-specific fence presets (5 NM CTR, approach corridors, ILS critical areas)

### Phase 3: Safety Integration
- [ ] Add runway exclusion barrier certificate to S1 `barrier` module
- [ ] Wire furia-core abort rules into S1 `safety_gate()`
- [ ] Add airport-specific EMStop triggers

### Phase 4: Guidance Integration
- [ ] Wire `compute_intercept_point()` into S1 guidance via furia_bridge
- [ ] Add intercept waypoint generation to S1 `guidance::commands`

### Phase 5: MAVLink Integration
- [ ] Replace S1 MAVLink stub with furia-core `MavlinkCommandEncoder`
- [ ] Add heartbeat emission
- [ ] Add mission upload capability

### Phase 6: Task Allocation Integration
- [ ] Wire furia-core CBBA for effector-to-target assignment
- [ ] Keep S1 market-based allocation for mission tasking

### Phase 7: World Model Integration
- [ ] Ingest `FusedMultiModalTrack` from furia-core into S1 world model
- [ ] Add classification confidence to S1 track types

## Bordeaux Airport Geometry (for S1 presets)

```rust
// BOD CTR: 5 NM radius
const BOD_CTR_RADIUS_MM: i64 = 9_260_000; // 5 NM in mm
const BOD_CTR_CENTER_LAT_MM: i64 = 44_828_333; // 44.828333° × 1e6
const BOD_CTR_CENTER_LON_MM: i64 = -715_556;   // -0.715556° × 1e6

// Runway 05/23
const RWY_05_HEADING_CDEG: i16 = 4_600; // 46°
const RWY_23_HEADING_CDEG: i16 = 22_600; // 226°
const RWY_05_23_LENGTH_MM: i64 = 3_100_000; // 3,100 m

// Runway 11/29
const RWY_11_HEADING_CDEG: i16 = 11_400; // 114°
const RWY_29_HEADING_CDEG: i16 = 29_400; // 294°
const RWY_11_29_LENGTH_MM: i64 = 2_415_000; // 2,415 m

// ILS Critical Area (Runway 05)
const ILS_CRITICAL_WIDTH_MM: i64 = 300_000; // 300 m
const ILS_CRITICAL_LENGTH_MM: i64 = 600_000; // 600 m from threshold

// Approach/Departure Corridor
const APPROACH_CORRIDOR_WIDTH_MM: i64 = 500_000; // 500 m
const APPROACH_CORRIDOR_LENGTH_MM: i64 = 10_000_000; // 10 km
```