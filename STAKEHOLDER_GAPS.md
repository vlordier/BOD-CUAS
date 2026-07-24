# Demo Gap Analysis — Stakeholder View

## The Three Audiences

| Stakeholder | Primary Concern | Will Ask | 
|---|---|---|
| **DGAC** (civil aviation authority) | Safety, non-interference with commercial aviation, regulatory compliance, audit trail | "Does this make my airport safer or just more complicated?" |
| **Military** | Threat credibility, ROE clarity, C2 decisiveness, interoperability | "Can I trust this in a real engagement?" |
| **C-UAS Operator** | Situational awareness, cognitive load, clear decisions, fail-safe defaults | "What do I do next and why?" |

---

## Critical Gaps

### 1. No Operator Decision UI

**What's there:** The replay publishes `operator.action.authorized` at 40s. There is no actual operator interface — the authorization just happens automatically.

**What's needed:** An operator decision panel that:
- Shows the track with threat assessment
- Requires explicit "Authorize Interception" button press
- Shows a confirmation dialog with: track ID, threat level, authorization scope, consequences
- Logs the operator decision with timestamp
- Has a "Deny" option that produces a different outcome

**Why it matters to DGAC:** "Who authorized this? When? What were they looking at? Was there a confirmation step?"

### 2. No Protected Volume Visualization on the Map

**What's there:** Protected volumes defined in `threat-origin.yaml`, stored in Core state, but **never rendered on the C2 map**.

**What's needed:**
- Semi-transparent red/orange/yellow zones over runway approach paths
- Visual indication when a track enters a protected volume (zone highlight, track color change)
- Altitude band indicators
- "Violation" alert with distance-to-boundary

**Why it matters to DGAC:** "Show me exactly what airspace this system protects and how you know a track violated it."

### 3. No Safety Conflict Visualization

**What's there:** At 70s, `safety.civilian_aircraft_conflict` triggers Core to publish `swarm.command.abort`. The C2 receives the abort command but there's no visual conflict indicator on the map.

**What's needed:**
- Civilian aircraft track rendered in a distinct color (e.g., blue) with flight ID label
- Collision prediction line between civilian aircraft and UAS track
- Red "CONFLICT" warning box with: flight ID, track ID, separation distance, time to conflict
- When abort is issued, clear visual transition (track turns red, status shows ABORTED)

**Why it matters to military:** "Prove you won't shoot down a civilian airliner. Show me the conflict assessment and the abort decision."

### 4. No C-UAS Symbology

**What's there:** Generic map symbols (circles with labels). No distinction between threat types.

**What's needed (NATO MIL-STD-2525C or equivalent):**
- Cooperative UAS: blue diamond with "U" inside
- Non-cooperative UAS: red diamond with "U" inside
- Unknown UAS: yellow diamond with "?" inside
- Crewed aircraft: blue filled circle
- Threat track with velocity vector line
- Track trail (history dots)
- Sensor coverage arcs/cones

**Why it matters to operators:** "I need to know at a glance: friend, foe, neutral, unknown. I don't have time to read labels."

### 5. No Authority Delegation Visualization

**What's there:** The delegation is published on `furia.s1.mission-delegation` with `valid_until_ms`, `authority.mode`, etc. The C2 shows a countdown bar, but doesn't show the *spatial* or *operational* boundaries of the delegation.

**What's needed:**
- On the map: a dashed circle showing the permitted volume (where S1 can operate)
- A text overlay: "BOUNDED AUTHORITY: track & shadow only — no kinetic effects"
- When lost link triggers: "LOST LINK — continuing within existing authority envelope (300s remaining)"
- When abort triggers: "AUTHORITY REVOKED — safety hold"

**Why it matters to military:** "What exactly is my drone allowed to do? What happens if it loses link? Who pulls the trigger on abort?"

### 6. No Audio Feedback

**What's there:** Silent UI. Events appear as text in the timeline.

**What's needed:**
- Audible alert on delegation received
- Audible warning on lost link
- Urgent audible alert on civilian conflict
- Distinct abort sound
- Ability to mute

**Why it matters to operators:** "In a real operation, I'm not staring at the screen. I need audio cues."

### 7. No Post-Demo Summary

**What's there:** Three verifier logs with PASS/FAIL. No visual debrief.

**What's needed (shown on C2 after scenario completes):**
- Timeline with all key events in chronological order
- Metrics: detection-to-delegation time, delegation-to-abort time, lost-link duration, total scenario duration
- Engagement chain visualization: DETECTED → ASSESSED → AUTHORIZED → DELEGATED → EXECUTING → LOST LINK → RECOVERED → ABORTED → SAFE HOLD
- Map replay (playback of entire scenario)

**Why it matters to DGAC:** "Show me the complete audit trail. Every decision, every authorization, every state change."

### 8. No Airport Context Map

**What's there:** Generic OSM tiles. No airport-specific overlay.

**What's needed:**
- Bordeaux LFBD runway layout (05/23, 11/29)
- Taxiway labels
- Approach path lines (ILS corridors)
- Terminal/parking area
- Airport boundary fence
- Restricted airspace zones

**Why it matters to DGAC:** "Does this system know where my runways are? Can it track a UAS approaching runway 23?"

### 9. No Operator Workflow Demonstration

**What's there:** The demonstration is fully automated. The operator never makes a decision.

**What's needed (for the demo only — not production):**
- Split the demo into phases with "pause for operator" points
- At each pause, show the operator's options and let the presenter explain the decision
- Resume to show the consequence of the decision

**Why it matters to everyone:** "A fully automated demo proves the code works. A demo with operator decisions proves the system is usable."

---

## Prioritized Action Plan

### High Impact, Low Effort (can add in <2h each)

| # | Feature | Status | Files affected |
|---|---------|--------|---------------|
| 1 | Audio alerts | ✅ Done | `CuasInfoPanel.tsx` |
| 2 | Protected volume rendering | ✅ Done | `Console.tsx` |
| 3 | Safety conflict marker | ✅ Done | `Console.tsx`, `CuasInfoPanel.tsx` |
| 4 | Post-demo summary card | ✅ Done | `CuasInfoPanel.tsx` |
| 5 | Authority envelope on map | ✅ Done | `Console.tsx` |
| 6 | Comms status indicator | ✅ Done | `CuasInfoPanel.tsx` |

### High Impact, Medium Effort (4-8h each)

| # | Feature | What to build |
|---|---------|---------------|
| 7 | Operator decision panel | Modal UI that requires explicit "Authorize Interception" button press before delegation |
| 8 | C-UAS symbology | NATO-style threat symbols (diamonds, filled/unfilled, color-coded) |
| 9 | Track trail / velocity vectors | Show last N positions as trail dots + velocity arrow on map |
| 10 | French language labels | i18n support for French UI labels |

### High Impact, High Effort (weeks)

| # | Feature | What to build |
|---|---------|---------------|
| 11 | Bordeaux airport map overlay | Import LFBD geodata (runways, taxiways, approach paths) |
| 12 | Scenario playback | Record all NATS messages and replay with speed controls |
| 13 | Full operator console | Dedicated operator workstation UI with track table, decision queue, comms panel |

---

## Recommended Demo Script (Revised)

```
Phase 1 (0-25s): "The system detects a non-cooperative UAS approaching 
  Bordeaux runway 23. Multiple sensors converge on the target."
  → Show: map with track, sensor bearing lines, protected volume

Phase 2 (25-40s): "Core assesses the threat. The track has entered a 
  protected volume. Operator authorization is required."
  → Show: threat assessment panel, "Authorize?" button

Phase 3 (40-50s): "The operator authorizes interception. Core delegates 
  bounded authority to S1 — track & shadow only, no kinetic effects."
  → Show: delegation card, authority envelope on map, countdown starts

Phase 4 (50-60s): "Communications are lost. S1 continues within the 
  existing authority envelope — bounded continuation, not new authority."
  → Show: lost link indicator, countdown continues, envelope unchanged

Phase 5 (60-70s): "Communications restored. S1 resumes normal execution."
  → Show: green status, timeline marker

Phase 6 (70-90s): "A civilian aircraft conflicts with the response 
  volume. Core issues safety abort. S1 reaches SafeHold."
  → Show: civilian aircraft track, conflict warning, abort command, 
     final ABORTED/SAFEHOLD state

Phase 7 (90s+): "Scenario complete. Full audit trail available."
  → Show: post-demo summary with metrics
```