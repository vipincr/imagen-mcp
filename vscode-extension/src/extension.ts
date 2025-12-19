import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as cp from "child_process";
import * as os from "os";

const SERVER_ID = "imagen";
const DEFAULT_MODEL = "gemini-3-pro-image-preview";
const VENV_DIR_NAME = ".imagen-venv";

const API_KEY_INPUT_BASE_ID = "imagen-google-ai-api-key";
const API_KEY_INPUT_VERSION_KEY = "imagenMcp.apiKeyInputVersion";

// Python dependencies needed by the server
const PYTHON_DEPENDENCIES = [
  "fastmcp>=2.0.0",
  "Pillow>=10.4.0",
  "pillow-heif>=0.18.0",
];

function getWorkspaceRoot(): string | undefined {
  const folder = vscode.workspace.workspaceFolders?.[0];
  return folder?.uri.fsPath;
}

function getApiKeyInputId(context: vscode.ExtensionContext): string {
  const version = context.globalState.get<number>(API_KEY_INPUT_VERSION_KEY, 1);
  return `${API_KEY_INPUT_BASE_ID}-v${version}`;
}

async function bumpApiKeyInputId(context: vscode.ExtensionContext): Promise<string> {
  const current = context.globalState.get<number>(API_KEY_INPUT_VERSION_KEY, 1);
  const next = current + 1;
  await context.globalState.update(API_KEY_INPUT_VERSION_KEY, next);
  return `${API_KEY_INPUT_BASE_ID}-v${next}`;
}

function getWorkspaceMcpPath(): string | undefined {
  const root = getWorkspaceRoot();
  if (!root) return undefined;
  return path.join(root, ".vscode", "mcp.json");
}

function getWorkspaceSettingsPath(): string | undefined {
  const root = getWorkspaceRoot();
  if (!root) return undefined;
  return path.join(root, ".vscode", "settings.json");
}

function cleanupLeakedKeysSync(): void {
  // Best-effort cleanup of previously leaked keys in workspace files.
  // Must not throw during activation.
  try {
    const mcpPath = getWorkspaceMcpPath();
    if (mcpPath && fs.existsSync(mcpPath)) {
      const raw = fs.readFileSync(mcpPath, "utf8");
      const json = JSON.parse(raw);
      const imagenServer = json?.servers?.[SERVER_ID];
      if (imagenServer?.env?.GOOGLE_AI_API_KEY) {
        delete imagenServer.env.GOOGLE_AI_API_KEY;
        // If env is now empty, drop it.
        if (imagenServer.env && Object.keys(imagenServer.env).length === 0) {
          delete imagenServer.env;
        }
        fs.writeFileSync(mcpPath, JSON.stringify(json, null, 2), "utf8");
      }
    }
  } catch {
    // ignore
  }

  try {
    const settingsPath = getWorkspaceSettingsPath();
    if (settingsPath && fs.existsSync(settingsPath)) {
      const raw = fs.readFileSync(settingsPath, "utf8");
      const json = JSON.parse(raw);
      if (typeof json?.["imagenMcp.apiKey"] === "string" && json["imagenMcp.apiKey"].trim()) {
        delete json["imagenMcp.apiKey"];
        fs.writeFileSync(settingsPath, JSON.stringify(json, null, 2), "utf8");
      }
    }
  } catch {
    // ignore
  }
}


/**
 * Get the path to the extension's bundled server directory.
 */
function getBundledServerPath(context: vscode.ExtensionContext): string {
  return path.join(context.extensionPath, "server");
}

/**
 * Get the path where we store the virtual environment.
 * Uses VS Code's global storage path so it persists across workspaces.
 */
function getVenvPath(context: vscode.ExtensionContext): string {
  return path.join(context.globalStorageUri.fsPath, VENV_DIR_NAME);
}

/**
 * Get the Python executable path within the virtual environment.
 */
function getVenvPython(context: vscode.ExtensionContext): string {
  const venvPath = getVenvPath(context);
  const isWindows = os.platform() === "win32";
  return isWindows
    ? path.join(venvPath, "Scripts", "python.exe")
    : path.join(venvPath, "bin", "python");
}

/**
 * Find a Python 3 interpreter on the system.
 */
async function findPython3(): Promise<string | undefined> {
  const candidates = os.platform() === "win32"
    ? ["python", "python3", "py -3"]
    : ["python3", "python"];
  
  for (const candidate of candidates) {
    try {
      const result = await execCommand(`${candidate} --version`);
      if (result.includes("Python 3")) {
        return candidate.split(" ")[0]; // Return just "python3" or "python", not "py -3"
      }
    } catch {
      // Try next candidate
    }
  }
  return undefined;
}

/**
 * Execute a command and return stdout.
 */
function execCommand(command: string, cwd?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    cp.exec(command, { cwd, timeout: 120000 }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(`${error.message}\n${stderr}`));
      } else {
        resolve(stdout);
      }
    });
  });
}

/**
 * Check if the virtual environment exists and is valid.
 */
async function isVenvValid(context: vscode.ExtensionContext): Promise<boolean> {
  const pythonPath = getVenvPython(context);
  try {
    await fs.promises.access(pythonPath, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

/**
 * Check if a marker file indicates dependencies are installed.
 */
async function areDependenciesInstalled(context: vscode.ExtensionContext): Promise<boolean> {
  const markerPath = path.join(getVenvPath(context), ".deps-installed");
  try {
    await fs.promises.access(markerPath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

/**
 * Write a marker file to indicate dependencies are installed.
 */
async function markDependenciesInstalled(context: vscode.ExtensionContext): Promise<void> {
  const markerPath = path.join(getVenvPath(context), ".deps-installed");
  await fs.promises.writeFile(markerPath, new Date().toISOString(), "utf8");
}

/**
 * Ensure the Python environment is set up with all dependencies.
 */
async function ensurePythonEnvironment(context: vscode.ExtensionContext): Promise<boolean> {
  const venvPath = getVenvPath(context);
  const pythonPath = getVenvPython(context);

  // Ensure global storage directory exists
  await fs.promises.mkdir(context.globalStorageUri.fsPath, { recursive: true });

  // Check if venv already exists and is valid
  if (await isVenvValid(context) && await areDependenciesInstalled(context)) {
    return true;
  }

  // Find Python 3
  const systemPython = await findPython3();
  if (!systemPython) {
    vscode.window.showErrorMessage(
      "Python 3 is required but not found. Please install Python 3 and try again."
    );
    return false;
  }

  // Show progress while setting up
  return vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Imagen MCP: Setting up Python environment...",
      cancellable: false,
    },
    async (progress) => {
      try {
        // Create virtual environment if needed
        if (!(await isVenvValid(context))) {
          progress.report({ message: "Creating virtual environment..." });
          await execCommand(`${systemPython} -m venv "${venvPath}"`);
        }

        // Upgrade pip
        progress.report({ message: "Upgrading pip..." });
        await execCommand(`"${pythonPath}" -m pip install --upgrade pip`);

        // Install dependencies
        progress.report({ message: "Installing dependencies..." });
        for (const dep of PYTHON_DEPENDENCIES) {
          await execCommand(`"${pythonPath}" -m pip install "${dep}"`);
        }

        // Mark dependencies as installed
        await markDependenciesInstalled(context);

        vscode.window.showInformationMessage("Imagen MCP: Python environment ready.");
        return true;
      } catch (error) {
        vscode.window.showErrorMessage(
          `Imagen MCP: Failed to set up Python environment: ${error}`
        );
        return false;
      }
    }
  );
}

/**
 * Get the server command and args for the MCP config.
 * Uses the bundled server from the extension.
 */
function getServerConfig(context: vscode.ExtensionContext): { command: string; args: string[] } {
  const pythonPath = getVenvPython(context);
  const serverPath = path.join(getBundledServerPath(context), "run_server.py");
  return {
    command: pythonPath,
    args: [serverPath],
  };
}

async function setApiKey(context: vscode.ExtensionContext) {
  // We cannot programmatically overwrite VS Code's stored MCP input value.
  // To let users correct a bad key without editing JSON, we bump the input id,
  // causing VS Code to prompt again next time the server starts.
  await bumpApiKeyInputId(context);
  await ensureMcpConfig(context, { force: true, notify: true });
  vscode.window.showInformationMessage(
    "Imagen MCP: API key will be requested again when the server starts (key stored securely by VS Code)."
  );
}

async function promptForApiKeyIfMissing(context: vscode.ExtensionContext) {
  // VS Code will prompt for the input when the MCP server starts.
  // We only ensure the MCP config exists.
  await ensureMcpConfig(context, { force: false, notify: false });
}

function updateStatusBar(status: vscode.StatusBarItem) {
  const config = vscode.workspace.getConfiguration();
  const current = config.get<string>("imagenMcp.modelId") || DEFAULT_MODEL;
  status.text = `$(rocket) Imagen: ${current}`;
}

async function setModel(context: vscode.ExtensionContext, status: vscode.StatusBarItem) {
  const config = vscode.workspace.getConfiguration();
  const current = config.get<string>("imagenMcp.modelId") || DEFAULT_MODEL;
  const picks = [
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
    "gemini-2.0-flash-exp-image-generation",
    "imagen-4.0-generate-001",
    "imagen-4.0-ultra-generate-001"
  ];

  const selection = await vscode.window.showQuickPick(picks, {
    placeHolder: "Select default image model",
    canPickMany: false
  });

  if (!selection) {
    return;
  }

  await config.update("imagenMcp.modelId", selection, vscode.ConfigurationTarget.Workspace);
  vscode.window.showInformationMessage(`Imagen MCP model set to ${selection}.`);
  updateStatusBar(status);
  await ensureMcpConfig(context, { force: true, notify: false });
}

async function writeMcpConfig(context: vscode.ExtensionContext) {
  await ensureMcpConfig(context, { force: true, notify: true });
}

/**
 * Reinstall the Python environment from scratch.
 */
async function reinstallEnvironment(context: vscode.ExtensionContext) {
  const venvPath = getVenvPath(context);
  
  // Remove existing venv
  try {
    await fs.promises.rm(venvPath, { recursive: true, force: true });
  } catch {
    // Ignore errors if directory doesn't exist
  }
  
  // Reinstall
  const success = await ensurePythonEnvironment(context);
  if (success) {
    // Regenerate MCP config with new paths
    await ensureMcpConfig(context, { force: true, notify: true });
  }
}

async function ensureMcpConfig(
  context: vscode.ExtensionContext,
  options: { force?: boolean; notify?: boolean } = {}
) {
  const root = getWorkspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage("No workspace folder open.");
    return;
  }

  const vscodeDir = path.join(root, ".vscode");
  const mcpPath = path.join(vscodeDir, "mcp.json");

  // Check if we need to migrate from old workspace-based config
  let needsMigration = false;
  if (fs.existsSync(mcpPath)) {
    try {
      const existing = JSON.parse(await fs.promises.readFile(mcpPath, "utf8"));
      const imagenServer = existing?.servers?.[SERVER_ID];
      if (imagenServer) {
        const cmd = imagenServer.command || "";
        // Detect old workspace-based configs that need migration
        if (cmd.includes("${workspaceFolder}") || cmd.includes("run_with_venv.sh") || cmd.includes("run_server.py")) {
          needsMigration = true;
        }
      }
    } catch {
      // If we can't parse, let's regenerate
      needsMigration = true;
    }
  }

  if (!options.force && !needsMigration && fs.existsSync(mcpPath)) {
    return; // already present and doesn't need migration
  }

  // Ensure the Python environment is set up before writing the MCP config
  const envReady = await ensurePythonEnvironment(context);
  if (!envReady) {
    return; // Error already shown by ensurePythonEnvironment
  }

  const config = vscode.workspace.getConfiguration();
  const modelId = config.get<string>("imagenMcp.modelId") || DEFAULT_MODEL;

  // Get the bundled server configuration
  const serverConfig = getServerConfig(context);

  const mcpConfig = {
    inputs: [
      {
        id: getApiKeyInputId(context),
        type: "promptString",
        description: "Google AI API key for Imagen/Gemini image generation",
        password: true
      }
    ],
    servers: {
      [SERVER_ID]: {
        command: serverConfig.command,
        args: serverConfig.args,
        env: {
          GOOGLE_AI_API_KEY: "${input:" + getApiKeyInputId(context) + "}",
          IMAGEN_MODEL_ID: modelId,
        },
      },
    },
  };

  await fs.promises.mkdir(vscodeDir, { recursive: true });
  await fs.promises.writeFile(mcpPath, JSON.stringify(mcpConfig, null, 2), "utf8");

  if (options.notify || needsMigration) {
    vscode.window.showInformationMessage(
      needsMigration 
        ? `Imagen MCP config migrated to use bundled server: ${mcpPath}` 
        : `MCP config written to ${mcpPath}`
    );
  }
}

export function activate(context: vscode.ExtensionContext) {
  // First: remove any leaked keys from workspace files (best effort).
  cleanupLeakedKeysSync();

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
  status.text = `$(rocket) Imagen MCP`;
  status.tooltip = "Imagen MCP Server";
  status.command = "imagenMcp.setModel";
  status.show();

  context.subscriptions.push(
    vscode.commands.registerCommand("imagenMcp.setApiKey", () => setApiKey(context)),
    vscode.commands.registerCommand("imagenMcp.setModel", () => setModel(context, status)),
    vscode.commands.registerCommand("imagenMcp.writeMcpConfig", () => writeMcpConfig(context)),
    vscode.commands.registerCommand("imagenMcp.reinstallEnvironment", () => reinstallEnvironment(context)),
    status
  );

  updateStatusBar(status);

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (event.affectsConfiguration("imagenMcp.modelId")) {
        updateStatusBar(status);
      }
      if (event.affectsConfiguration("imagenMcp")) {
        await ensureMcpConfig(context, { force: true, notify: false });
      }
    })
  );

  // Auto-create MCP config if missing so the server works out of the box
  void (async () => {
    await ensureMcpConfig(context, { force: false, notify: false });
    await promptForApiKeyIfMissing(context);
  })();
}

export function deactivate() {}
