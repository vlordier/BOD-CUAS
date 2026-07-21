# BOD-CUAS contract fixtures

These files are example provider and operational-event payloads for the Bordeaux-Merignac C-UAS scenario.

The authoritative schemas live in `vlordier/furia-core/docs/contracts`:

- `provider-capabilities.schema.json`
- `operational-events.schema.json`

BOD-CUAS does not own or fork those schemas. It supplies scenario-specific fixtures that must remain valid against the Core versions.

Integration rule:

`BOD-CUAS -> furia-core provider boundary -> furia-c2 OperationalEventStream -> @furia/ui`

UI code must not import BOD-CUAS scenario implementation details directly.
