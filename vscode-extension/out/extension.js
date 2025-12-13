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
const SERVER_ID = "imagen";
const API_KEY_SECRET = "imagenMcp.apiKey";
const DEFAULT_MODEL = "gemini-3-pro-image-preview";
const DEFAULT_SCRIPT = "run_with_venv.sh";
const LEGACY_CMD = "python";
const LEGACY_ARGS = ["${workspaceFolder}/run_server.py"];
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
async function ensureExecutableIfNeeded(command, root) {
    const resolved = command.replace("${workspaceFolder}", root);
    const scriptName = path.basename(resolved);
    if (scriptName !== DEFAULT_SCRIPT) {
        return;
    }
    try {
        await fs.promises.access(resolved, fs.constants.F_OK);
        await fs.promises.chmod(resolved, 0o755);
    }
    catch {
        // Silently ignore if script missing; user may have custom command.
    }
}
async function maybeMigrateLegacyServerConfig(config) {
    const cmd = config.get("imagenMcp.serverCommand");
    const args = config.get("imagenMcp.serverArgs") || [];
    const isLegacy = cmd === LEGACY_CMD && JSON.stringify(args) === JSON.stringify(LEGACY_ARGS);
    if (!isLegacy) {
        return false;
    }
    await config.update("imagenMcp.serverCommand", "${workspaceFolder}/" + DEFAULT_SCRIPT, vscode.ConfigurationTarget.Workspace);
    await config.update("imagenMcp.serverArgs", [], vscode.ConfigurationTarget.Workspace);
    return true;
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
async function ensureMcpConfig(context, options = {}) {
    const root = getWorkspaceRoot();
    if (!root) {
        vscode.window.showErrorMessage("No workspace folder open.");
        return;
    }
    const vscodeDir = path.join(root, ".vscode");
    const mcpPath = path.join(vscodeDir, "mcp.json");
    const initialConfig = vscode.workspace.getConfiguration();
    const migrated = await maybeMigrateLegacyServerConfig(initialConfig);
    const config = migrated ? vscode.workspace.getConfiguration() : initialConfig;
    const apiKey = await getApiKey(context.secrets);
    const modelId = config.get("imagenMcp.modelId") || DEFAULT_MODEL;
    const serverCommand = config.get("imagenMcp.serverCommand") || "${workspaceFolder}/" + DEFAULT_SCRIPT;
    const serverArgs = config.get("imagenMcp.serverArgs") || [];
    if (!options.force && fs.existsSync(mcpPath) && !migrated) {
        return; // already present and no migration triggered
    }
    await ensureExecutableIfNeeded(serverCommand, root);
    const mcpConfig = {
        servers: {
            [SERVER_ID]: {
                command: serverCommand,
                args: serverArgs,
                env: {
                    ...(apiKey ? { GOOGLE_AI_API_KEY: apiKey } : {}),
                    IMAGEN_MODEL_ID: modelId,
                },
            },
        },
    };
    await fs.promises.mkdir(vscodeDir, { recursive: true });
    await fs.promises.writeFile(mcpPath, JSON.stringify(mcpConfig, null, 2), "utf8");
    if (options.notify) {
        vscode.window.showInformationMessage(`MCP config written to ${mcpPath}`);
    }
}
function activate(context) {
    const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 10);
    status.text = `$(rocket) Imagen MCP`;
    status.tooltip = "Imagen MCP Server";
    status.command = "imagenMcp.setModel";
    status.show();
    context.subscriptions.push(vscode.commands.registerCommand("imagenMcp.setApiKey", () => setApiKey(context)), vscode.commands.registerCommand("imagenMcp.setModel", () => setModel(context, status)), vscode.commands.registerCommand("imagenMcp.writeMcpConfig", () => writeMcpConfig(context)), status);
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