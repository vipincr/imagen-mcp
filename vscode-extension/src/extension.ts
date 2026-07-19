import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as cp from "child_process";
import * as os from "os";

const SERVER_ID = "imagen";
const SERVER_LABEL = "Imagen (Google AI)";
const PROVIDER_ID = "imagenMcp.serverProvider";
const DEFAULT_MODEL = "gemini-3-pro-image";
const VENV_DIR_NAME = ".imagen-venv";

// Global SecretStorage key for the Google AI API key. This is stored by VS Code
// in the OS keychain and is shared across every workspace and window.
const SECRET_API_KEY = "imagenMcp.googleAiApiKey";

// Python dependencies needed by the server.
const PYTHON_DEPENDENCIES = [
  "fastmcp>=2.0.0",
  "Pillow>=10.4.0",
  "pillow-heif>=0.18.0",
];

const AVAILABLE_MODELS = [
  "gemini-3-pro-image", // Nano Banana Pro (GA) — highest quality, default
  "gemini-3-pro-image-preview", // Nano Banana Pro (preview)
  "gemini-3.1-flash-image", // Nano Banana 2 — faster
  "gemini-2.5-flash-image", // Nano Banana
  "imagen-4.0-ultra-generate-001", // Imagen 4 Ultra
  "imagen-4.0-generate-001", // Imagen 4
];

// ---------------------------------------------------------------------------
// Python environment management (stored in extension global storage, shared
// across all workspaces).
// ---------------------------------------------------------------------------

function getVenvPath(context: vscode.ExtensionContext): string {
  return path.join(context.globalStorageUri.fsPath, VENV_DIR_NAME);
}

function getVenvPython(context: vscode.ExtensionContext): string {
  const venvPath = getVenvPath(context);
  return os.platform() === "win32"
    ? path.join(venvPath, "Scripts", "python.exe")
    : path.join(venvPath, "bin", "python");
}

function getServerScript(context: vscode.ExtensionContext): string {
  return path.join(context.extensionPath, "server", "run_server.py");
}

function execCommand(command: string, cwd?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    cp.exec(command, { cwd, timeout: 180000 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(`${error.message}\n${stderr}`));
      } else {
        resolve(stdout);
      }
    });
  });
}

async function findPython3(): Promise<string | undefined> {
  const candidates =
    os.platform() === "win32" ? ["python", "python3", "py -3"] : ["python3", "python"];
  for (const candidate of candidates) {
    try {
      const result = await execCommand(`${candidate} --version`);
      if (result.includes("Python 3")) {
        return candidate.split(" ")[0];
      }
    } catch {
      // try next candidate
    }
  }
  return undefined;
}

async function pathExists(p: string, mode: number): Promise<boolean> {
  try {
    await fs.promises.access(p, mode);
    return true;
  } catch {
    return false;
  }
}

function depsMarkerPath(context: vscode.ExtensionContext): string {
  return path.join(getVenvPath(context), ".deps-installed");
}

/**
 * Ensure the Python virtual environment exists and dependencies are installed.
 * Safe to call repeatedly; returns true when the environment is ready.
 */
async function ensurePythonEnvironment(context: vscode.ExtensionContext): Promise<boolean> {
  const venvPath = getVenvPath(context);
  const pythonPath = getVenvPython(context);

  await fs.promises.mkdir(context.globalStorageUri.fsPath, { recursive: true });

  const venvReady = await pathExists(pythonPath, fs.constants.X_OK);
  const depsReady = await pathExists(depsMarkerPath(context), fs.constants.F_OK);
  if (venvReady && depsReady) {
    return true;
  }

  const systemPython = await findPython3();
  if (!systemPython) {
    vscode.window.showErrorMessage(
      "Imagen MCP: Python 3 is required but was not found. Please install Python 3 and reload."
    );
    return false;
  }

  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Imagen MCP: Setting up Python environment…",
      cancellable: false,
    },
    async (progress) => {
      try {
        if (!(await pathExists(pythonPath, fs.constants.X_OK))) {
          progress.report({ message: "Creating virtual environment…" });
          await execCommand(`${systemPython} -m venv "${venvPath}"`);
        }
        progress.report({ message: "Upgrading pip…" });
        await execCommand(`"${pythonPath}" -m pip install --upgrade pip`);
        progress.report({ message: "Installing dependencies…" });
        for (const dep of PYTHON_DEPENDENCIES) {
          await execCommand(`"${pythonPath}" -m pip install "${dep}"`);
        }
        await fs.promises.writeFile(depsMarkerPath(context), new Date().toISOString(), "utf8");
        return true;
      } catch (error) {
        vscode.window.showErrorMessage(`Imagen MCP: Failed to set up Python environment: ${error}`);
        return false;
      }
    }
  );
}

async function reinstallEnvironment(
  context: vscode.ExtensionContext,
  onChange: () => void
): Promise<void> {
  try {
    await fs.promises.rm(getVenvPath(context), { recursive: true, force: true });
  } catch {
    // ignore
  }
  const ok = await ensurePythonEnvironment(context);
  if (ok) {
    vscode.window.showInformationMessage("Imagen MCP: Python environment reinstalled.");
    onChange();
  }
}

// ---------------------------------------------------------------------------
// API key management (global SecretStorage) + validation.
// ---------------------------------------------------------------------------

/**
 * Validate a Google AI API key with a lightweight models.list request.
 * Returns true when the key is accepted by the API.
 */
async function validateApiKey(key: string): Promise<boolean> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${encodeURIComponent(
    key
  )}`;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    // Network failure: don't hard-fail validation, treat as "unknown/accept".
    return true;
  }
}

/**
 * Prompt the user for an API key, validate it, and store it in global
 * SecretStorage. Returns the stored key, or undefined if the user cancelled.
 */
async function promptAndStoreApiKey(
  context: vscode.ExtensionContext,
  opts: { reason?: string } = {}
): Promise<string | undefined> {
  for (;;) {
    const entered = await vscode.window.showInputBox({
      title: "Imagen MCP: Google AI API Key",
      prompt:
        opts.reason ??
        "Enter your Google AI (Gemini) API key. It is stored securely in your OS keychain and shared across all workspaces.",
      password: true,
      ignoreFocusOut: true,
      placeHolder: "AIza…",
    });

    if (entered === undefined) {
      return undefined; // user cancelled
    }
    const key = entered.trim();
    if (!key) {
      opts.reason = "API key cannot be empty. Enter your Google AI API key.";
      continue;
    }

    const valid = await vscode.window.withProgress(
      { location: vscode.ProgressLocation.Notification, title: "Imagen MCP: Validating API key…" },
      () => validateApiKey(key)
    );

    if (!valid) {
      const choice = await vscode.window.showWarningMessage(
        "Imagen MCP: That API key was rejected by Google AI.",
        "Try Again",
        "Save Anyway",
        "Cancel"
      );
      if (choice === "Cancel" || choice === undefined) {
        return undefined;
      }
      if (choice === "Try Again") {
        opts.reason = "Re-enter your Google AI API key.";
        continue;
      }
      // "Save Anyway" falls through
    }

    await context.secrets.store(SECRET_API_KEY, key);
    return key;
  }
}

// ---------------------------------------------------------------------------
// One-time migration: strip previously leaked keys from workspace files that
// older versions of this extension may have written.
// ---------------------------------------------------------------------------

function cleanupLeakedWorkspaceFiles(): void {
  const root = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (!root) {
    return;
  }
  const mcpPath = path.join(root, ".vscode", "mcp.json");
  try {
    if (fs.existsSync(mcpPath)) {
      const json = JSON.parse(fs.readFileSync(mcpPath, "utf8"));
      const server = json?.servers?.[SERVER_ID];
      // If this file was written by an old version of the extension, remove the
      // imagen entry (and the file if it becomes empty) — the server is now
      // registered globally by the extension, not via a workspace file.
      if (server) {
        delete json.servers[SERVER_ID];
        if (Array.isArray(json.inputs)) {
          json.inputs = json.inputs.filter(
            (i: { id?: string }) => !String(i?.id ?? "").startsWith("imagen-google-ai-api-key")
          );
          if (json.inputs.length === 0) {
            delete json.inputs;
          }
        }
        const emptyServers = json.servers && Object.keys(json.servers).length === 0;
        if (emptyServers) {
          delete json.servers;
        }
        if (!json.servers && !json.inputs) {
          fs.rmSync(mcpPath, { force: true });
        } else {
          fs.writeFileSync(mcpPath, JSON.stringify(json, null, 2), "utf8");
        }
      }
    }
  } catch {
    // best effort — never block activation
  }
}

// ---------------------------------------------------------------------------
// Status bar.
// ---------------------------------------------------------------------------

function currentModel(): string {
  return vscode.workspace.getConfiguration().get<string>("imagenMcp.modelId") || DEFAULT_MODEL;
}

function updateStatusBar(status: vscode.StatusBarItem): void {
  status.text = `$(sparkle) Imagen: ${currentModel()}`;
  status.tooltip = "Imagen MCP — click to change the default image model";
}

async function setModel(status: vscode.StatusBarItem, onChange: () => void): Promise<void> {
  const selection = await vscode.window.showQuickPick(AVAILABLE_MODELS, {
    placeHolder: "Select the default image model",
    canPickMany: false,
  });
  if (!selection) {
    return;
  }
  // Store globally so the choice applies to every workspace.
  await vscode.workspace
    .getConfiguration()
    .update("imagenMcp.modelId", selection, vscode.ConfigurationTarget.Global);
  updateStatusBar(status);
  onChange();
}

// ---------------------------------------------------------------------------
// Activation.
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  // Best-effort migration for users upgrading from the workspace-file design.
  cleanupLeakedWorkspaceFiles();

  const didChange = new vscode.EventEmitter<void>();
  context.subscriptions.push(didChange);
  const fireChange = () => didChange.fire();

  // Status bar.
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  status.command = "imagenMcp.setModel";
  updateStatusBar(status);
  status.show();
  context.subscriptions.push(status);

  // The MCP server definition provider — this is what registers the server
  // globally (across all workspaces) and gives it a managed entry, icon, and
  // settings gear in the MCP panel. No workspace files are written.
  const provider: vscode.McpServerDefinitionProvider<vscode.McpStdioServerDefinition> = {
    onDidChangeMcpServerDefinitions: didChange.event,

    // Called eagerly by the editor — must NOT require user interaction.
    provideMcpServerDefinitions: async () => {
      return [
        new vscode.McpStdioServerDefinition(
          SERVER_LABEL,
          getVenvPython(context),
          [getServerScript(context)],
          {
            IMAGEN_MODEL_ID: currentModel(),
          },
          context.extension.packageJSON.version
        ),
      ];
    },

    // Called when the editor is about to start the server — here we may do
    // heavy work and prompt the user.
    resolveMcpServerDefinition: async (server) => {
      const ready = await ensurePythonEnvironment(context);
      if (!ready) {
        return undefined; // env error already surfaced
      }

      let key = await context.secrets.get(SECRET_API_KEY);
      if (!key) {
        key = await promptAndStoreApiKey(context);
        if (!key) {
          vscode.window.showErrorMessage(
            "Imagen MCP: No API key provided — the server will not start. Run “Imagen MCP: Set API Key” to configure it."
          );
          return undefined;
        }
      }

      server.env = {
        ...server.env,
        GOOGLE_AI_API_KEY: key,
        IMAGEN_MODEL_ID: currentModel(),
      };
      return server;
    },
  };

  context.subscriptions.push(
    vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, provider)
  );

  // Commands.
  context.subscriptions.push(
    vscode.commands.registerCommand("imagenMcp.setApiKey", async () => {
      const key = await promptAndStoreApiKey(context, {
        reason: "Enter a new Google AI API key (replaces any existing key).",
      });
      if (key) {
        vscode.window.showInformationMessage(
          "Imagen MCP: API key saved. Restart the Imagen server from the MCP panel to apply it."
        );
        fireChange();
      }
    }),
    vscode.commands.registerCommand("imagenMcp.clearApiKey", async () => {
      await context.secrets.delete(SECRET_API_KEY);
      vscode.window.showInformationMessage("Imagen MCP: Stored API key cleared.");
      fireChange();
    }),
    vscode.commands.registerCommand("imagenMcp.setModel", () => setModel(status, fireChange)),
    vscode.commands.registerCommand("imagenMcp.reinstallEnvironment", () =>
      reinstallEnvironment(context, fireChange)
    )
  );

  // React to model changes made through the Settings UI.
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("imagenMcp.modelId")) {
        updateStatusBar(status);
        fireChange();
      }
    })
  );

  // If the key changes in another window, re-resolve the server.
  context.subscriptions.push(
    context.secrets.onDidChange((e) => {
      if (e.key === SECRET_API_KEY) {
        fireChange();
      }
    })
  );
}

export function deactivate(): void {
  /* no-op */
}
