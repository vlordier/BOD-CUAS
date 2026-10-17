.PHONY: demo golden capture doctor clean

# Bordeaux C-UAS Golden Demo — one-command entry points

demo golden: ## Run the full golden demo end-to-end
	GOLDEN_EXIT_AFTER_ACCEPTANCE=1 bash demo/golden/smoke.sh

capture: ## Run the live demo and capture C2 authority transitions
	node demo/golden/capture_c2.mjs

doctor: ## Check prerequisites for the golden demo
	bash demo/golden/doctor.sh

clean: ## Leave unrelated processes and shared temporary state untouched
	@echo "The golden runner stops only its own children on exit and removes its private NATS state."
	@echo "No global process or temporary-directory cleanup is performed."

nats-state-isolation-check:
	bash demo/golden/test_nats_state_isolation.sh
