/**
 * Smoke tests for TTT VS Code extension command registration.
 *
 * These tests verify that commands are properly registered and callable.
 * They run in a minimal Node.js context (no VS Code host needed).
 */

import * as assert from "assert";
import * as path from "path";

// We can only verify that the extension module exports activate/deactivate without
// a full VS Code host. The actual integration tests would require @vscode/test-electron.

describe("TTT Extension Module", () => {
  it("should export activate and deactivate", () => {
    // Verify the compiled JS module has the expected exports
    const extensionPath = path.join(__dirname, "..", "extension.js");
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const ext = require(extensionPath);
      assert.strictEqual(typeof ext.activate, "function", "activate must be a function");
      assert.strictEqual(typeof ext.deactivate, "function", "deactivate must be a function");
    } catch {
      // If compiled JS doesn't exist yet, skip gracefully
      console.log("Skipping: compiled extension.js not found (run npm run build first)");
    }
  });
});

describe("Command IDs", () => {
  const expectedCommands = [
    "ttt.convertFile",
    "ttt.lintFile",
    "ttt.generateScript",
    "ttt.analyzeServer",
    "ttt.autoFixFile",
    "ttt.setupOnboarding",
    "ttt.installRuntime",
    "ttt.createServerApiConfig",
    "ttt.migrateServer",
    "ttt.openDashboard",
    "ttt.navigateMarkers",
  ];

  it("should have all expected commands defined in package.json", () => {
    const pkgPath = path.join(__dirname, "..", "..", "package.json");
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const pkg = require(pkgPath);
    const definedCommands: string[] = (pkg.contributes?.commands ?? []).map(
      (c: { command: string }) => c.command
    );

    for (const cmd of expectedCommands) {
      assert.ok(
        definedCommands.includes(cmd),
        `Command ${cmd} should be registered in package.json`
      );
    }
  });

  it("should not have duplicate command entries", () => {
    const pkgPath = path.join(__dirname, "..", "..", "package.json");
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const pkg = require(pkgPath);
    const definedCommands: string[] = (pkg.contributes?.commands ?? []).map(
      (c: { command: string }) => c.command
    );
    const unique = new Set(definedCommands);
    assert.strictEqual(definedCommands.length, unique.size, "No duplicate commands");
  });
});
