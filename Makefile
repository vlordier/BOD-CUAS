.PHONY: demo golden doctor clean

# Bordeaux C-UAS Golden Demo — one-command entry points

demo golden: ## Run the full golden demo end-to-end
	GOLDEN_EXIT_AFTER_ACCEPTANCE=1 bash demo/golden/smoke.sh

doctor: ## Check prerequisites for the golden demo
	bash demo/golden/doctor.sh

clean: ## Kill all demo processes and clean state
	# Kill by binary path to avoid broad pkill -f matches
	-pkill -f "^/Users/vincent/Work/furia-core/target/release/counter-uas-director" 2>/dev/null || true
	-pkill -f "^/Users/vincent/Work/furia-core/target/release/furia-core-server" 2>/dev/null || true
	-pkill -f "^/Users/vincent/Work/furia-core/target/release/dev-atak-server" 2>/dev/null || true
	-pkill -f "^/Users/vincent/Work/S1/target/release/s1-sim-server" 2>/dev/null || true
	-pkill -f "^/Users/vincent/Work/S1/target/release/cuas-health-injector" 2>/dev/null || true
	-pkill -f "^/Users/vincent/Work/furia-core/target/release/sapient-simulator" 2>/dev/null || true
	-pkill -f "^nats-server" 2>/dev/null || true
	-pkill -f "^npx vite" 2>/dev/null || true
	-pkill -f "verify.py" 2>/dev/null || true
	-pkill -f "replay.py" 2>/dev/null || true
	rm -rf /tmp/furia-bod-nats-js $${TMPDIR:-/tmp}/furia-bod-golden 2>/dev/null || true
	@echo "Cleaned up demo state"