.PHONY: demo golden resilience-check capture doctor airport-pack-check airport-pack-build-check airport-pack-resolve-check geospatial-provenance-check geospatial-readiness-audit geospatial-import-contract-check geospatial-acquisition-queue current-airport-reference-check live-context-check hybrid-context-check simulated-context simulated-video simulated-world static-context-check acquire-bati3d verify-bati3d bati3d-index bati3d-core bati3d-web ownership-check clean

# Bordeaux C-UAS Golden Demo — one-command entry points

demo golden: ## Run the full golden demo end-to-end
	GOLDEN_EXIT_AFTER_ACCEPTANCE=1 bash demo/golden/smoke.sh

resilience-check: ## Validate deterministic fault-injection scenarios and coverage
	python3 -m unittest discover -s demo/resilience -p 'test_*.py'
	python3 demo/resilience/coverage.py --check
	python3 demo/resilience/run_pack.py --check

capture: ## Run the live demo and capture C2 authority transitions
	node demo/golden/capture_c2.mjs

doctor: ## Check prerequisites for the golden demo
	# ATAK auto-runs when :8080 is free and degrades cleanly when occupied.
	DEMO_ATAK_MODE=auto bash demo/golden/doctor.sh

airport-pack-check: ## Validate the generic airport-pack boundary and LFBD fixture
	python3 scripts/validate_airport_pack.py demo/golden/airport-packs/lfbd/manifest.json

geospatial-provenance-check: ## Validate DEM/building provenance and the French airport registry
	python3 scripts/validate_geospatial_provenance.py --manifest data/geospatial/lfbd/manifest.json --registry data/geospatial/france-airports-registry.json
	python3 -m unittest scripts/test_geospatial_provenance.py

geospatial-readiness-audit: ## Audit every inventoried airport without fabricating packs
	python3 scripts/audit_airport_geospatial_readiness.py --output data/geospatial/france-airports-readiness-audit.json

geospatial-import-contract-check: ## Verify the generic airport geodata importer without network access
	python3 -m unittest scripts/test_import_airport_open_data.py

geospatial-acquisition-queue: ## Build the explicit acquisition queue for all inventoried airports
	python3 scripts/build_geospatial_acquisition_queue.py --inventory data/geospatial/france-airports-identity-inventory.json --current-reference data/geospatial/france-airports-current-reference.json --output data/geospatial/france-airports-acquisition-queue.json

current-airport-reference-check: ## Validate a downloaded current airport reference export
	python3 -m unittest scripts/test_import_current_airport_reference.py

airport-pack-build-check: ## Verify source configuration can build a generic airport pack
	@tmp=$$(mktemp -d "$(CURDIR)/.airport-pack-check.XXXXXX"); trap 'rm -rf "$$tmp"' EXIT; python3 scripts/build_airport_pack.py config/airport-pack-builder.example.json --output "$$tmp/pack" >/dev/null; python3 scripts/validate_airport_pack.py "$$tmp/pack/manifest.json"

repository-boundary-check: ## Verify cross-repository ownership and import boundaries
	python3 scripts/check_repository_boundaries.py

ownership-check: ## Validate explicit ownership of LFBD profiles, scenarios, stories and fixtures
	python3 scripts/validate_lfbd_ownership.py

runtime-config-check: ## Validate the shared golden-demo runtime configuration
	bash demo/golden/test_runtime_config.sh
	bash demo/golden/test_nats_state_isolation.sh
	python3 -m unittest demo/golden/test_replay_configuration.py
	python3 -m unittest demo/golden/test_airport_pack.py

airport-pack-resolve-check: ## Resolve an airport-pack into runner-ready JSON
	python3 scripts/resolve_airport_pack.py demo/golden/airport-packs/lfbd/manifest.json >/tmp/bod-cuas-resolved-pack.json
	python3 -m unittest demo/golden/test_airport_pack_resolution.py

live-context-check: ## Validate local ADS-B/Remote-ID adapter fixtures
	python3 -m unittest demo/live-context/test_context_bridge.py demo/live-context/test_source_catalog.py demo/live-context/test_real_context_adapter.py

hybrid-context-check: ## Validate the public-context adapter and guided scenario without network access
	python3 -m unittest demo/live-context/test_real_context_adapter.py demo/live-context/test_hybrid_demo_scenario.py

simulated-context: ## Publish labelled external-context simulators to local NATS
	python3 demo/live-context/context_simulator.py

simulated-video: ## Publish continuous labelled EO/IR metadata to local NATS
	python3 demo/live-context/eo_ir_simulator.py

simulated-world: ## Publish the labelled Bati3D/RealGazebo visual-world descriptor
	python3 demo/live-context/visual_world_simulator.py

static-context-check: ## Validate the versioned static-context import boundary
	python3 demo/live-context/static_context_import.py --manifest demo/live-context/static-context-source.example.json --output /tmp/furia-lfbd-static-context.json

acquire-bati3d: ## Download the bounded public 2012 Bati3D context pack for LFBD
	bash demo/live-context/acquire_lfbd_bati3d.sh

verify-bati3d: ## Verify the acquired Bati3D archive
	bash demo/live-context/acquire_lfbd_bati3d.sh --verify

bati3d-index: ## Index verified Bati3D geometry without extracting it
	python3 demo/live-context/prepare_lfbd_bati3d.py --index data/lfbd/bati3d/index.json

bati3d-core: ## Extract bounded historical 1.4 x 1 km LFBD core for reviewed Unreal import
	python3 demo/live-context/prepare_lfbd_bati3d.py --index data/lfbd/bati3d/index.json --extract-dir data/lfbd/bati3d/extracted-core $(foreach tile,x77y117 x77y118 x77y119 x77y120 x77y121 x78y117 x78y118 x78y119 x78y120 x78y121 x79y117 x79y118 x79y119 x79y120 x79y121 x80y117 x80y118 x80y119 x80y120 x80y121 x81y117 x81y118 x81y119 x81y120 x81y121 x82y117 x82y118 x82y119 x82y120 x82y121 x83y117 x83y118 x83y119 x83y120 x83y121,--subtile $(tile))

bati3d-web: ## Convert the bounded Bati3D core to browser-loadable GLB tiles
	python3 scripts/build_lfbd_bati3d_web.py

clean: ## Leave unrelated processes and shared temporary state untouched
	@echo "The golden runner stops only its own children on exit and removes its private NATS state."
	@echo "No global process or temporary-directory cleanup is performed."

nats-state-isolation-check:
	bash demo/golden/test_nats_state_isolation.sh
