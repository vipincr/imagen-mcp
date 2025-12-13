"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const cp = __importStar(require("child_process"));
const os = __importStar(require("os"));
const SERVER_ID = "imagen";
const API_KEY_SECRET = "imagenMcp.apiKey";
const DEFAULT_MODEL = "gemini-3-pro-image-preview";
const VENV_DIR_NAME = ".imagen-venv";
// Python dependencies needed by the server
const PYTHON_DEPENDENCIES = [
    "fastmcp>=2.0.0",
    "Pillow>=10.4.0",
    "pillow-heif>=0.18.0",
];
function getWorkspaceRoot() {
    const folder = vscode.workspace.workspaceFolders?.[0];
    return folder?.uri.fsPath;
}
async function getApiKey(secretStorage) {
    return secretStorage.get(API_KEY_SECRET);
}
function getConfiguredApiKey() {
    const config = vscode.workspace.getConfiguration();
    const raw = config.get("imagenMcp.apiKey");
    const trimmed = raw?.trim();
    return trimmed ? trimmed : undefined;
}
/**
 * Get the path to the extension's bundled server directory.
 */
function getBundledServerPath(context) {
    return path.join(context.extensionPath, "server");
}
/**
 * Get the path where we store the virtual environment.
 * Uses VS Code's global storage path so it persists across workspaces.
 */
function getVenvPath(context) {
    return path.join(context.globalStorageUri.fsPath, VENV_DIR_NAME);
}
/**
 * Get the Python executable path within the virtual environment.
 */
function getVenvPython(context) {
    const venvPath = getVenvPath(context);
    const isWindows = os.platform() === "win32";
    return isWindows
        ? path.join(venvPath, "Scripts", "python.exe")
        : path.join(venvPath, "bin", "python");
}
/**
 * Find a Python 3 interpreter on the system.
 */
async function findPython3() {
    const candidates = os.platform() === "win32"
        ? ["python", "python3", "py -3"]
        : ["python3", "python"];
    for (const candidate of candidates) {
        try {
            const result = await execCommand(`${candidate} --version`);
            if (result.includes("Python 3")) {
                return candidate.split(" ")[0]; // Return just "python3" or "python", not "py -3"
            }
        }
        catch {
            // Try next candidate
        }
    }
    return undefined;
}
/**
 * Execute a command and return stdout.
 */
function execCommand(command, cwd) {
    return new Promise((resolve, reject) => {
        cp.exec(command, { cwd, timeout: 120000 }, (error, stdout, stderr) => {
            if (error) {
                reject(new Error(`${error.message}\n${stderr}`));
            }
            else {
                resolve(stdout);
            }
        });
    });
}
/**
 * Check if the virtual environment exists and is valid.
 */
async function isVenvValid(context) {
    const pythonPath = getVenvPython(context);
    try {
        await fs.promises.access(pythonPath, fs.constants.X_OK);
        return true;
    }
    catch {
        return false;
    }
}
/**
 * Check if a marker file indicates dependencies are installed.
 */
async function areDependenciesInstalled(context) {
    const markerPath = path.join(getVenvPath(context), ".deps-installed");
    try {
        await fs.promises.access(markerPath, fs.constants.F_OK);
        return true;
    }
    catch {
        return false;
    }
}
/**
 * Write a marker file to indicate dependencies are installed.
 */
async function markDependenciesInstalled(context) {
    const markerPath = path.join(getVenvPath(context), ".deps-installed");
    await fs.promises.writeFile(markerPath, new Date().toISOString(), "utf8");
}
/**
 * Ensure the Python environment is set up with all dependencies.
 */
async function ensurePythonEnvironment(context) {
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
        vscode.window.showErrorMessage("Python 3 is required but not found. Please install Python 3 and try again.");
        return false;
    }
    // Show progress while setting up
    return vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: "Imagen MCP: Setting up Python environment...",
        cancellable: false,
    }, async (progress) => {
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
        }
        catch (error) {
            vscode.window.showErrorMessage(`Imagen MCP: Failed to set up Python environment: ${error}`);
            return false;
        }
    });
}
/**
 * Get the server command and args for the MCP config.
 * Uses the bundled server from the extension.
 */
function getServerConfig(context) {
    const pythonPath = getVenvPython(context);
    const serverPath = path.join(getBundledServerPath(context), "run_server.py");
    return {
        command: pythonPath,
        args: [serverPath],
    };
}
async function syncApiKeyFromSettings(context) {
    const configured = getConfiguredApiKey();
    if (configured) {
        await context.secrets.store(API_KEY_SECRET, configured);
        return configured;
    }
    // Keep any previously stored secret so extension updates or missing settings
    // do not wipe the API key. Users can explicitly clear via the command or by
    // overwriting the setting.
    return getApiKey(context.secrets);
}
async function setApiKey(context) {
    const apiKey = await vscode.window.showInputBox({
        prompt: "Enter your Google AI API key",
        password: true,
        ignoreFocusOut: true,
        placeHolder: "GOOGLE_AI_API_KEY"
    });
    if (!apiKey) {
        return;
    }
    await context.secrets.store(API_KEY_SECRET, apiKey.trim());
    await vscode.workspace.getConfiguration().update("imagenMcp.apiKey", apiKey.trim(), vscode.ConfigurationTarget.Workspace);
    vscode.window.showInformationMessage("Imagen MCP API key saved to VS Code secrets.");
}
async function promptForApiKeyIfMissing(context) {
    const existing = await getApiKey(context.secrets);
    if (existing) {
        return;
    }
    const choice = await vscode.window.showWarningMessage("Imagen MCP API key is not set. The server will fail without it.", "Set API Key");
    if (choice === "Set API Key") {
        await setApiKey(context);
        await ensureMcpConfig(context, { force: true, notify: false });
    }
}
function updateStatusBar(status) {
    const config = vscode.workspace.getConfiguration();
    const current = config.get("imagenMcp.modelId") || DEFAULT_MODEL;
    status.text = `$(rocket) Imagen: ${current}`;
}
async function setModel(context, status) {
    const config = vscode.workspace.getConfiguration();
    const current = config.get("imagenMcp.modelId") || DEFAULT_MODEL;
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
async function writeMcpConfig(context) {
    await syncApiKeyFromSettings(context);
    await ensureMcpConfig(context, { force: true, notify: true });
}
/**
 * Reinstall the Python environment from scratch.
 */
async function reinstallEnvironment(context) {
    const venvPath = getVenvPath(context);
    // Remove existing venv
    try {
        await fs.promises.rm(venvPath, { recursive: true, force: true });
    }
    catch {
        // Ignore errors if directory doesn't exist
    }
    // Reinstall
    const success = await ensurePythonEnvironment(context);
    if (success) {
        // Regenerate MCP config with new paths
        await ensureMcpConfig(context, { force: true, notify: true });
    }
}
async function ensureMcpConfig(context, options = {}) {
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
        }
        catch {
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
    const apiKey = await getApiKey(context.secrets);
    const modelId = config.get("imagenMcp.modelId") || DEFAULT_MODEL;
    // Get the bundled server configuration
    const serverConfig = getServerConfig(context);
    const mcpConfig = {
        servers: {
            [SERVER_ID]: {
                command: serverConfig.command,
                args: serverConfig.args,
                env: {
                    ...(apiKey ? { GOOGLE_AI_API_KEY: apiKey } : {}),
                    IMAGEN_MODEL_ID: modelId,
                },
            },
        },
    };
    await fs.promises.mkdir(vscodeDir, { recursive: true });
    await fs.promises.writeFile(mcpPath, JSON.stringify(mcpConfig, null, 2), "utf8");
    if (options.notify || needsMigration) {
        vscode.window.showInformationMessage(needsMigration
            ? `Imagen MCP config migrated to use bundled server: ${mcpPath}`
            : `MCP config written to ${mcpPath}`);
    }
}
function activate(context) {
    const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
    status.text = `$(rocket) Imagen MCP`;
    status.tooltip = "Imagen MCP Server";
    status.command = "imagenMcp.setModel";
    status.show();
    context.subscriptions.push(vscode.commands.registerCommand("imagenMcp.setApiKey", () => setApiKey(context)), vscode.commands.registerCommand("imagenMcp.setModel", () => setModel(context, status)), vscode.commands.registerCommand("imagenMcp.writeMcpConfig", () => writeMcpConfig(context)), vscode.commands.registerCommand("imagenMcp.reinstallEnvironment", () => reinstallEnvironment(context)), status);
    updateStatusBar(status);
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(async (event) => {
        if (event.affectsConfiguration("imagenMcp.apiKey")) {
            await syncApiKeyFromSettings(context);
            await promptForApiKeyIfMissing(context);
        }
        if (event.affectsConfiguration("imagenMcp.modelId")) {
            updateStatusBar(status);
        }
        if (event.affectsConfiguration("imagenMcp")) {
            await ensureMcpConfig(context, { force: true, notify: false });
        }
    }));
    // Auto-create MCP config if missing so the server works out of the box
    void (async () => {
        await syncApiKeyFromSettings(context);
        await ensureMcpConfig(context, { force: false, notify: false });
        await promptForApiKeyIfMissing(context);
    })();
}
function deactivate() { }
//# sourceMappingURL=extension.js.map