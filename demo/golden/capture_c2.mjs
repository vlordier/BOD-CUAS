#!/usr/bin/env node
/**
 * Capture the live Bordeaux C-UAS C2 flow with Playwright.
 *
 * This starts the same multi-repository runtime as `make demo`, opens the
 * browser version of the Tauri frontend, and records the operator view at
 * meaningful authority transitions. It is intentionally not a mocked UI.
 *
 * Usage:
 *   SKIP_BUILD=1 node demo/golden/capture_c2.mjs
 *   make capture
 */

import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import net from "node:net";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { chromium } from "playwright";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const defaultOutputDir = path.join(
  process.env.TMPDIR || "/tmp",
  "furia-bod-golden-captures",
);
const outputDir = path.resolve(process.env.C2_CAPTURE_DIR || defaultOutputDir);
const c2Url = process.env.C2_CAPTURE_URL || "http://127.0.0.1:4180/console/tactical-cuas-cell";
const readyPattern = "FURIA BORDEAUX GOLDEN DEMO RUNNING";
const natsHost = process.env.C2_CAPTURE_NATS_HOST || "127.0.0.1";
const natsPort = Number(process.env.C2_CAPTURE_NATS_PORT || "4222");

function startDemo() {
  const child = spawn("bash", ["run.sh"], {
    cwd: scriptDir,
    env: {
      ...process.env,
      GOLDEN_EXIT_AFTER_ACCEPTANCE: "1",
      // The release capture is deliberately full-speed deterministic. Keep
      // inherited shell/demo settings from compressing the authority timeline.
      DEMO_SPEED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  let output = "";
  const append = (chunk) => {
    const text = chunk.toString();
    output += text;
    process.stdout.write(text);
  };
  child.stdout.on("data", append);
  child.stderr.on("data", append);

  return { child, output: () => output };
}

async function waitFor(check, label, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${label}`);
}

async function capture(page, name) {
  const file = path.join(outputDir, name);
  await page.screenshot({ path: file, fullPage: true, animations: "disabled" });
  console.log(`  captured ${file}`);
}

/**
 * Observes Core/S1 outputs over the NATS TCP wire protocol. This is read-only:
 * capture points are anchored to authoritative messages, never elapsed time or
 * a label that happens to already exist in the UI.
 */
function observeAuthoritativeTransitions() {
  const transitions = {
    delegation: false,
    lostLink: false,
    abort: false,
    safeHold: false,
  };
  const socket = net.createConnection({ host: natsHost, port: natsPort });
  let buffer = Buffer.alloc(0);
  let pendingMessage = null;

  const processBuffer = () => {
    while (true) {
      if (pendingMessage) {
        if (buffer.length < pendingMessage.byteCount + 2) return;
        const payload = buffer.subarray(0, pendingMessage.byteCount);
        buffer = buffer.subarray(pendingMessage.byteCount + 2);
        const subject = pendingMessage.subject;
        pendingMessage = null;
        try {
          const message = JSON.parse(payload.toString("utf8"));
          if (subject === "furia.s1.mission-delegation") transitions.delegation = true;
          if (
            subject === "furia.s1.execution-evidence" &&
            message.state === "active" &&
            message.degraded_mode === "lost_link_continuation"
          ) {
            transitions.lostLink = true;
          }
          if (subject === "swarm.command.abort" && message.policy_id === "BOD-RWY-FRATRICIDE-003") {
            transitions.abort = true;
          }
          if (
            subject === "furia.s1.execution-evidence" &&
            message.state === "aborted" &&
            message.degraded_mode === "safety_hold" &&
            message.rejection_reason === "core_safety_abort" &&
            message.active_constraint_ids?.includes("BOD-RWY-FRATRICIDE-003")
          ) {
            transitions.safeHold = true;
          }
        } catch {
          // Ignore malformed payloads; the actual transition will never be inferred.
        }
        continue;
      }

      const lineEnd = buffer.indexOf("\r\n");
      if (lineEnd === -1) return;
      const line = buffer.subarray(0, lineEnd).toString("utf8");
      buffer = buffer.subarray(lineEnd + 2);
      if (line.startsWith("PING")) socket.write("PONG\r\n");
      if (line.startsWith("MSG ")) {
        const [, subject, , byteCount] = line.split(" ");
        const parsedByteCount = Number(byteCount);
        if (subject && Number.isFinite(parsedByteCount) && parsedByteCount >= 0) {
          pendingMessage = { subject, byteCount: parsedByteCount };
        }
      }
    }
  };

  const ready = new Promise((resolve, reject) => {
    socket.once("connect", () => {
      socket.write('CONNECT {"verbose":false,"pedantic":false}\r\n');
      socket.write("SUB furia.s1.mission-delegation 1\r\n");
      socket.write("SUB furia.s1.execution-evidence 2\r\n");
      socket.write("SUB swarm.command.abort 3\r\n");
      resolve();
    });
    socket.once("error", reject);
  });
  socket.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    processBuffer();
  });

  return {
    ready,
    close: () => socket.destroy(),
    has: (transition) => transitions[transition],
  };
}

async function connectAuthoritativeObserver() {
  const deadline = Date.now() + 30_000;
  let lastError;
  while (Date.now() < deadline) {
    const observer = observeAuthoritativeTransitions();
    try {
      await observer.ready;
      return observer;
    } catch (error) {
      observer.close();
      lastError = error;
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }
  throw new Error(`Timed out connecting read-only NATS observer: ${lastError?.message ?? "unknown error"}`);
}

async function requireUiState(page, locator, label, timeoutMs = 15_000) {
  try {
    await locator.waitFor({ state: "visible", timeout: timeoutMs });
  } catch {
    throw new Error(`C2 did not render required ${label}`);
  }
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  console.log("=== Bordeaux C-UAS live C2 capture ===");
  console.log(`Output: ${outputDir}`);

  const demo = startDemo();
  let transitions;
  let browser;

  try {
    transitions = await connectAuthoritativeObserver();
    await transitions.ready;
    await waitFor(
      () => demo.output().includes(readyPattern),
      "golden demo readiness",
      120_000,
    );

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();
    const browserErrors = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") browserErrors.push(message.text());
    });
    await page.goto(c2Url, { waitUntil: "networkidle", timeout: 30_000 });
    try {
      await requireUiState(
        page,
        page.locator('[aria-label="Bordeaux C-UAS incident workspace"]'),
        "Bordeaux C-UAS workspace",
        30_000,
      );
      await requireUiState(page, page.getByText(/TRACK 4660/), "selected non-cooperative track");
    } catch {
      await capture(page, "00-c2-render-failure.png");
      throw new Error(`C2 operational workspace did not render: ${browserErrors.join(" | ") || "no browser error reported"}`);
    }
    await capture(page, "01-operational-picture.png");

    await waitFor(() => transitions.has("delegation"), "authoritative mission delegation", 60_000);
    try {
      await requireUiState(page, page.getByText(/Authorized.*exercise-authority/), "delegated authority state");
    } catch (error) {
      await capture(page, "02-bounded-delegation-failure.png");
      throw error;
    }
    await capture(page, "02-bounded-delegation.png");

    await waitFor(() => transitions.has("lostLink"), "authoritative lost-link continuation evidence", 30_000);
    await requireUiState(page, page.getByText(/Authorized.*exercise-authority/), "authority retained during bounded continuation");
    await requireUiState(page, page.getByText("No safety interlock active", { exact: true }), "pre-abort safety state");
    await capture(page, "03-lost-link-continuation.png");

    await waitFor(() => transitions.has("abort"), "authoritative safety abort command", 30_000);
    await waitFor(() => transitions.has("safeHold"), "contract-correlated S1 safe-hold evidence", 30_000);
    await requireUiState(page, page.getByText("Predicted civilian conflict inhibits intercept", { exact: true }), "safety inhibition reason");
    await requireUiState(page, page.getByText("SAFE-HOLD CONFIRMED", { exact: true }), "safe-hold acknowledgement state");
    await capture(page, "04-civilian-conflict-safety-abort.png");

    if (browserErrors.length > 0) {
      throw new Error(`C2 reported browser errors during capture: ${browserErrors.join(" | ")}`);
    }

    await context.close();
  } finally {
    await browser?.close();
    transitions?.close();
    if (!demo.child.killed) demo.child.kill("SIGTERM");
  }

  console.log("=== C2 capture complete ===");
}

main().catch((error) => {
  console.error(`C2 capture failed: ${error.message}`);
  process.exitCode = 1;
});
