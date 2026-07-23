.PHONY: demo golden doctor clean

# Bordeaux C-UAS Golden Demo — one-command entry points

demo golden: ## Run the full golden demo end-to-end
	GOLDEN_EXIT_AFTER_ACCEPTANCE=1 bash demo/golden/smoke.sh

doctor: ## Check prerequisites for the golden demo
	bash demo/golden/doctor.sh

clean: ## Kill all demo processes and clean state
	-pkill -f "counter-uas-director" 2>/dev/null || true
	-pkill -f "furia-core-server" 2>/dev/null || true
	-pkill -f "dev-atak-server" 2>/dev/null || true
	-pkill -f "s1-sim-server" 2>/dev/null || true
	-pkill -f "cuas-health-injector" 2>/dev/null || true
	-pkill -f "sapient-simulator" 2>/dev/null || true
	-pkill -f "nats-server" 2>/dev/null || true
	-pkill -f "npx vite" 2>/dev/null || true
	-pkill -f "verify.py" 2>/dev/null || true
	-pkill -f "replay.py" 2>/dev/null || true
	rm -rf /tmp/furia-bod-nats-js /tmp/furia-bod-golden 2>/dev/null || true
	@echo "Cleaned up demo state"