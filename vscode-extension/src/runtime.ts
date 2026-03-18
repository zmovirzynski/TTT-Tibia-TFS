import * as vscode from "vscode";
import * as os from "os";
import * as path from "path";
import { createWriteStream } from "fs";
import { promises as fs } from "fs";
import * as https from "https";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

export type RuntimeMode = "auto" | "embedded" | "python";

export type TttExecution = {
  command: string;
  baseArgs: string[];
  mode: "embedded" | "python";
};

function getAssetName(platform: NodeJS.Platform, arch: string): string | undefined {
  if (platform === "win32" && arch === "x64") {
    return "ttt-runtime-win-x64.zip";
  }
  if (platform === "linux" && arch === "x64") {
    return "ttt-runtime-linux-x64.tar.gz";
  }
  if (platform === "darwin" && arch === "x64") {
    return "ttt-runtime-macos-x64.tar.gz";
  }
  if (platform === "darwin" && arch === "arm64") {
    return "ttt-runtime-macos-arm64.tar.gz";
  }
  return undefined;
}

export async function installEmbeddedRuntime(
  context: vscode.ExtensionContext,
  workspaceFolder: vscode.WorkspaceFolder
): Promise<string> {
  const cfg = vscode.workspace.getConfiguration("ttt", workspaceFolder.uri);
  const baseUrl = cfg.get<string>(
    "runtimeBaseUrl",
    "https://github.com/zmovirzynski/TTT-Tibia-TFS-Transpiler/releases/latest/download"
  ) as string;

  const asset = getAssetName(os.platform(), os.arch());
  if (!asset) {
    throw new Error(`Unsupported platform/arch: ${os.platform()} ${os.arch()}`);
  }

  const runtimeRoot = path.join(context.globalStorageUri.fsPath, "runtime", `${os.platform()}-${os.arch()}`);
  const archivePath = path.join(context.globalStorageUri.fsPath, asset);
  const downloadUrl = `${baseUrl}/${asset}`;

  await fs.mkdir(context.globalStorageUri.fsPath, { recursive: true });
  await fs.mkdir(runtimeRoot, { recursive: true });

  await downloadFile(downloadUrl, archivePath);

  if (asset.endsWith(".zip")) {
    await extractZip(archivePath, runtimeRoot);
  } else if (asset.endsWith(".tar.gz")) {
    await extractTarGz(archivePath, runtimeRoot);
  } else {
    throw new Error(`Unsupported runtime archive format: ${asset}`);
  }

  const executableName = os.platform() === "win32" ? "ttt.exe" : "ttt";
  const runtimePath = await findFileRecursive(runtimeRoot, executableName);
  if (!runtimePath) {
    throw new Error(`Runtime executable not found after extraction: ${executableName}`);
  }

  if (os.platform() !== "win32") {
    await fs.chmod(runtimePath, 0o755);
  }

  await cfg.update("runtimePath", runtimePath, vscode.ConfigurationTarget.Workspace);
  await cfg.update("runtimeMode", "embedded", vscode.ConfigurationTarget.Workspace);

  return runtimePath;
}

export async function resolveTttExecution(
  context: vscode.ExtensionContext,
  workspaceFolder: vscode.WorkspaceFolder
): Promise<TttExecution> {
  const cfg = vscode.workspace.getConfiguration("ttt", workspaceFolder.uri);
  const mode = cfg.get<RuntimeMode>("runtimeMode", "auto");
  const configuredRuntimePath = cfg.get<string>("runtimePath", "");

  if ((mode === "embedded" || mode === "auto") && configuredRuntimePath) {
    try {
      await fs.access(configuredRuntimePath);
      return {
        command: configuredRuntimePath,
        baseArgs: [],
        mode: "embedded",
      };
    } catch {
      // fallback to python mode below
    }
  }

  if (mode === "embedded") {
    throw new Error("Embedded runtime mode is enabled but runtimePath is invalid.");
  }

  const python = cfg.get<string>("pythonCommand", "python") as string;
  const runPyPath = cfg.get<string>("runPyPath", "run.py") as string;
  const runPyAbs = path.join(workspaceFolder.uri.fsPath, runPyPath);

  return {
    command: python,
    baseArgs: [runPyAbs],
    mode: "python",
  };
}

export function buildTerminalCommand(command: string, args: string[]): string {
  const quoted = [command, ...args].map(quoteShellArg);
  return quoted.join(" ");
}

function quoteShellArg(arg: string): string {
  if (/^[a-zA-Z0-9_./:-]+$/.test(arg)) {
    return arg;
  }
  return `"${arg.replace(/"/g, '\\"')}"`;
}

async function extractZip(archivePath: string, destination: string): Promise<void> {
  await execFileAsync(
    "powershell",
    [
      "-NoProfile",
      "-Command",
      `Expand-Archive -Path '${archivePath.replace(/'/g, "''")}' -DestinationPath '${destination.replace(/'/g, "''")}' -Force`
    ],
    { windowsHide: true }
  );
}

async function extractTarGz(archivePath: string, destination: string): Promise<void> {
  await execFileAsync("tar", ["-xzf", archivePath, "-C", destination], { windowsHide: true });
}

async function findFileRecursive(root: string, filename: string): Promise<string | undefined> {
  const entries = await fs.readdir(root, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(root, entry.name);
    if (entry.isFile() && entry.name.toLowerCase() === filename.toLowerCase()) {
      return full;
    }
    if (entry.isDirectory()) {
      const nested = await findFileRecursive(full, filename);
      if (nested) {
        return nested;
      }
    }
  }
  return undefined;
}

async function downloadFile(url: string, destination: string): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const request = https.get(url, (response) => {
      if (response.statusCode && response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        response.resume();
        downloadFile(response.headers.location, destination).then(resolve).catch(reject);
        return;
      }

      if (response.statusCode !== 200) {
        reject(new Error(`Download failed (${response.statusCode}) for ${url}`));
        response.resume();
        return;
      }

      const file = createWriteStream(destination);
      response.pipe(file);
      file.on("finish", () => {
        file.close();
        resolve();
      });
      file.on("error", reject);
    });

    request.on("error", reject);
  });
}
