import * as vscode from "vscode";
import { execFile } from "child_process";
import { promisify } from "util";
import * as path from "path";
import { findMethodDoc, getAllMethods, getMethodsForType } from "./tfsApi";
import {
  getTemplateConfigContent,
  loadServerApiConfig,
  ServerApiConfig,
} from "./serverApiConfig";
import {
  buildTerminalCommand,
  installEmbeddedRuntime,
  resolveTttExecution,
} from "./runtime";

const execFileAsync = promisify(execFile);
const DIAGNOSTIC_SOURCE = "TTT Lint";
let extensionCtx: vscode.ExtensionContext | undefined;

export function activate(context: vscode.ExtensionContext) {
  extensionCtx = context;
  const diagnostics = vscode.languages.createDiagnosticCollection("ttt-lint");
  context.subscriptions.push(diagnostics);

  context.subscriptions.push(registerCompletionProvider());
  context.subscriptions.push(registerHoverProvider());

  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      { language: "lua" },
      new TttQuickFixCodeActionProvider(),
      { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
    )
  );

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument(async (doc: vscode.TextDocument) => {
      if (doc.languageId !== "lua") {
        return;
      }
      const cfg = vscode.workspace.getConfiguration("ttt");
      if (!cfg.get<boolean>("lintOnSave", true)) {
        return;
      }
      await runLintForDocument(doc, diagnostics);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("ttt.convertFile", async () => runInTerminalForActiveFile("convert")),
    vscode.commands.registerCommand("ttt.lintFile", async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage("No active file to lint.");
        return;
      }
      await runLintForDocument(editor.document, diagnostics);
      vscode.window.showInformationMessage("TTT lint finished for active file.");
    }),
    vscode.commands.registerCommand("ttt.generateScript", async () => runGenerateScript()),
    vscode.commands.registerCommand("ttt.analyzeServer", async () => runAnalyzeServer()),
    vscode.commands.registerCommand("ttt.autoFixFile", async () => runInTerminalForActiveFile("fix")),
    vscode.commands.registerCommand("ttt.setupOnboarding", async () => runSetupOnboarding(context)),
    vscode.commands.registerCommand("ttt.installRuntime", async () => runInstallRuntime(context)),
    vscode.commands.registerCommand("ttt.createServerApiConfig", async () => createServerApiConfigFile())
  );

  maybePromptFirstRun(context);
}

export function deactivate() {}

function registerCompletionProvider(): vscode.Disposable {
  return vscode.languages.registerCompletionItemProvider(
    { language: "lua" },
    {
      async provideCompletionItems(document: vscode.TextDocument, position: vscode.Position) {
        const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
        const serverConfig = workspaceFolder ? await loadServerApiConfig(workspaceFolder) : emptyServerConfig();

        const line = document.lineAt(position.line).text.substring(0, position.character);
        if (line.trimStart().startsWith("--")) {
          return [];
        }

        const match = line.match(/\b([A-Za-z_][A-Za-z0-9_]*)\s*([:.])\s*([A-Za-z_]*)$/i);
        if (match) {
          const objectName = match[1];
          const prefix = (match[3] ?? "").toLowerCase();
          const typeHints = collectVariableTypeHints(document);
          const resolvedTypes = resolveObjectTypes(objectName, typeHints, serverConfig.aliases);

          const methods = resolvedTypes.length > 0
            ? resolvedTypes.flatMap((t) => getMethodsForType(t).concat(serverConfig.objects[t] ?? []))
            : getAllMethods().concat(getAllCustomObjectMethods(serverConfig));

          const uniqueByName = new Map<string, { method: string; detail: string; description: string }>();
          for (const method of methods) {
            if (!uniqueByName.has(method.method)) {
              uniqueByName.set(method.method, method);
            }
          }

          return [...uniqueByName.values()]
            .filter((m) => m.method.toLowerCase().startsWith(prefix))
            .map((m) => {
              const item = new vscode.CompletionItem(m.method, vscode.CompletionItemKind.Method);
              item.detail = m.detail;
              item.documentation = new vscode.MarkdownString(m.description);
              item.insertText = new vscode.SnippetString(`${m.method}($1)`);
              return item;
            });
        }

        const globalMatch = line.match(/\b([A-Za-z_][A-Za-z0-9_]*)$/);
        if (!globalMatch) {
          return [];
        }

        const globalPrefix = globalMatch[1].toLowerCase();
        if (!globalPrefix || serverConfig.globals.length === 0) {
          return [];
        }

        return serverConfig.globals
          .filter((g) => g.method.toLowerCase().startsWith(globalPrefix))
          .map((g) => {
            const item = new vscode.CompletionItem(g.method, vscode.CompletionItemKind.Function);
            item.detail = g.detail;
            item.documentation = new vscode.MarkdownString(g.description);
            item.insertText = new vscode.SnippetString(`${g.method}($1)`);
            return item;
          });
      }
    },
    ":",
    "."
  );
}

function registerHoverProvider(): vscode.Disposable {
  return vscode.languages.registerHoverProvider({ language: "lua" }, {
    async provideHover(document: vscode.TextDocument, position: vscode.Position) {
      const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
      const serverConfig = workspaceFolder ? await loadServerApiConfig(workspaceFolder) : emptyServerConfig();

      const range = document.getWordRangeAtPosition(position);
      if (!range) {
        return;
      }

      const method = document.getText(range);
      const lineText = document.lineAt(position.line).text;
      const before = lineText.slice(0, range.start.character);
      const contextMatch = before.match(/\b([A-Za-z_][A-Za-z0-9_]*)\s*[:.]\s*$/i);
      if (!contextMatch) {
        const globalDoc = serverConfig.globals.find((g) => g.method === method);
        if (!globalDoc) {
          return;
        }

        const md = new vscode.MarkdownString();
        md.appendCodeblock(globalDoc.detail, "lua");
        md.appendMarkdown(`\n${globalDoc.description}`);
        return new vscode.Hover(md, range);
      }

      const objectName = contextMatch[1];
      const typeHints = collectVariableTypeHints(document);
      const resolvedTypes = resolveObjectTypes(objectName, typeHints, serverConfig.aliases);

      let doc = undefined;
      for (const type of resolvedTypes) {
        doc = findMethodDoc(type, method);
        if (!doc) {
          doc = (serverConfig.objects[type] ?? []).find((m) => m.method === method);
        }
        if (doc) {
          break;
        }
      }
      if (!doc) {
        return;
      }

      const md = new vscode.MarkdownString();
      md.appendCodeblock(doc.detail, "lua");
      md.appendMarkdown(`\n${doc.description}`);
      return new vscode.Hover(md, range);
    }
  });
}

function collectVariableTypeHints(document: vscode.TextDocument): Map<string, string> {
  const hints = new Map<string, string>();

  for (let i = 0; i < document.lineCount; i += 1) {
    const line = document.lineAt(i).text;
    const match = line.match(/\blocal\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(Player|Creature|Item|Position|Npc)\s*\(/);
    if (match) {
      hints.set(match[1].toLowerCase(), match[2].toLowerCase());
    }
  }

  return hints;
}

function resolveObjectTypes(objectName: string, typeHints: Map<string, string>, customAliases: Record<string, string>): string[] {
  const name = objectName.toLowerCase();

  const direct = ["player", "creature", "item", "position", "game", "npc"];
  if (direct.includes(name)) {
    return [name];
  }

  if (typeHints.has(name)) {
    return [typeHints.get(name) as string];
  }

  const aliases: Record<string, string> = {
    p: "player",
    pl: "player",
    c: "creature",
    cr: "creature",
    i: "item",
    it: "item",
    pos: "position",
    np: "npc",
  };

  if (aliases[name]) {
    return [aliases[name]];
  }

  if (customAliases[name]) {
    return [customAliases[name]];
  }

  if (name) {
    return [name];
  }

  return [];
}

function getAllCustomObjectMethods(serverConfig: ServerApiConfig) {
  return Object.values(serverConfig.objects).flat();
}

function emptyServerConfig(): ServerApiConfig {
  return {
    objects: {},
    globals: [],
    aliases: {},
  };
}

class TttQuickFixCodeActionProvider implements vscode.CodeActionProvider {
  provideCodeActions(document: vscode.TextDocument, _range: vscode.Range, context: vscode.CodeActionContext): vscode.CodeAction[] {
    const hasTttDiagnostic = context.diagnostics.some((d: vscode.Diagnostic) => d.source === DIAGNOSTIC_SOURCE);
    if (!hasTttDiagnostic) {
      return [];
    }

    const action = new vscode.CodeAction("TTT: Auto-fix file", vscode.CodeActionKind.QuickFix);
    action.command = {
      title: "TTT: Auto-fix file",
      command: "ttt.autoFixFile"
    };
    action.isPreferred = true;

    return [action];
  }
}

async function runLintForDocument(document: vscode.TextDocument, diagnostics: vscode.DiagnosticCollection): Promise<void> {
  if (document.isUntitled || document.languageId !== "lua") {
    return;
  }

  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return;
  }

  const execution = await resolveTttExecutionForWorkspace(workspaceFolder);

  try {
    const { stdout } = await execFileAsync(execution.command, [
      ...execution.baseArgs,
      "lint",
      document.uri.fsPath,
      "--format",
      "json"
    ], {
      cwd: workspaceFolder.uri.fsPath,
      windowsHide: true
    });

    const parsed = JSON.parse(stdout) as {
      files?: Array<{
        filepath: string;
        issues: Array<{ line: number; column: number; severity: string; rule_id: string; message: string }>;
      }>;
    };

    const file = (parsed.files ?? [])[0];
    if (!file) {
      diagnostics.set(document.uri, []);
      return;
    }

    const diags = (file.issues ?? []).map((issue) => {
      const line = Math.max(0, (issue.line || 1) - 1);
      const col = Math.max(0, (issue.column || 1) - 1);
      const range = new vscode.Range(line, col, line, col + 1);

      let severity = vscode.DiagnosticSeverity.Information;
      if (issue.severity === "error" || issue.severity === "ERROR") {
        severity = vscode.DiagnosticSeverity.Error;
      } else if (issue.severity === "warning" || issue.severity === "WARNING") {
        severity = vscode.DiagnosticSeverity.Warning;
      } else if (issue.severity === "hint" || issue.severity === "HINT") {
        severity = vscode.DiagnosticSeverity.Hint;
      }

      const d = new vscode.Diagnostic(range, `${issue.rule_id}: ${issue.message}`, severity);
      d.source = DIAGNOSTIC_SOURCE;
      d.code = issue.rule_id;
      return d;
    });

    diagnostics.set(document.uri, diags);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showWarningMessage(`TTT lint failed: ${msg}`);
  }
}

async function runInTerminalForActiveFile(operation: "convert" | "fix") {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.isUntitled) {
    vscode.window.showWarningMessage("Open and save a file first.");
    return;
  }

  const workspaceFolder = vscode.workspace.getWorkspaceFolder(editor.document.uri);
  if (!workspaceFolder) {
    vscode.window.showWarningMessage("Open the file inside a workspace.");
    return;
  }

  const execution = await resolveTttExecutionForWorkspace(workspaceFolder);

  let args: string[] = [];
  if (operation === "fix") {
    args = [...execution.baseArgs, "fix", editor.document.uri.fsPath];
  } else {
    args = [
      ...execution.baseArgs,
      "convert",
      "-i",
      path.dirname(editor.document.uri.fsPath),
      "-o",
      `${path.dirname(editor.document.uri.fsPath)}_converted`,
      "-f",
      "tfs03",
      "-t",
      "revscript",
    ];
  }

  const terminal = vscode.window.createTerminal("TTT");
  terminal.show(true);
  terminal.sendText(buildTerminalCommand(execution.command, args));
}

async function runGenerateScript() {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) {
    vscode.window.showWarningMessage("Open a workspace to generate scripts.");
    return;
  }

  const type = await vscode.window.showQuickPick(
    ["action", "movement", "talkaction", "creaturescript", "globalevent", "spell", "npc"],
    { placeHolder: "Choose script type" }
  );
  if (!type) {
    return;
  }

  const name = await vscode.window.showInputBox({ prompt: "Script name", value: "new_script" });
  if (!name) {
    return;
  }

  const execution = await resolveTttExecutionForWorkspace(workspace);

  const terminal = vscode.window.createTerminal("TTT");
  terminal.show(true);
  terminal.sendText(
    buildTerminalCommand(execution.command, [
      ...execution.baseArgs,
      "create",
      "--type",
      type,
      "--name",
      name,
      "--output",
      workspace.uri.fsPath,
      "--format",
      "revscript",
    ])
  );
}

async function runAnalyzeServer() {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) {
    vscode.window.showWarningMessage("Open a workspace to analyze.");
    return;
  }

  const execution = await resolveTttExecutionForWorkspace(workspace);

  const terminal = vscode.window.createTerminal("TTT");
  terminal.show(true);
  terminal.sendText(
    buildTerminalCommand(execution.command, [
      ...execution.baseArgs,
      "analyze",
      workspace.uri.fsPath,
    ])
  );
}

async function runInstallRuntime(context: vscode.ExtensionContext): Promise<void> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) {
    vscode.window.showWarningMessage("Abra uma pasta de projeto antes de instalar o runtime.");
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "TTT: instalando runtime automático",
      cancellable: false,
    },
    async () => {
      const runtimePath = await installEmbeddedRuntime(context, workspace);
      vscode.window.showInformationMessage(`Runtime TTT instalado: ${runtimePath}`);
    }
  );
}

async function createServerApiConfigFile(): Promise<void> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) {
    vscode.window.showWarningMessage("Abra uma pasta de projeto antes de criar a config de API.");
    return;
  }

  const cfg = vscode.workspace.getConfiguration("ttt", workspace.uri);
  const relativePath = cfg.get<string>("serverApiConfigPath", ".ttt-server-api.json") as string;
  const uri = vscode.Uri.joinPath(workspace.uri, relativePath);

  try {
    await vscode.workspace.fs.stat(uri);
  } catch {
    const content = getTemplateConfigContent();
    await vscode.workspace.fs.writeFile(uri, Buffer.from(content, "utf-8"));
  }

  const doc = await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(doc, { preview: false });
  vscode.window.showInformationMessage("Config de API custom aberta. Edite e salve para atualizar autocomplete/hover.");
}

async function maybePromptFirstRun(context: vscode.ExtensionContext): Promise<void> {
  const done = context.globalState.get<boolean>("ttt.setupDone", false);
  if (done) {
    return;
  }

  const choice = await vscode.window.showInformationMessage(
    "TTT OTServ: quer configurar automaticamente agora?",
    "Configurar",
    "Depois"
  );

  if (choice === "Configurar") {
    await runSetupOnboarding(context);
  }
}

async function runSetupOnboarding(context: vscode.ExtensionContext): Promise<void> {
  const workspace = vscode.workspace.workspaceFolders?.[0];
  if (!workspace) {
    vscode.window.showWarningMessage("Abra uma pasta de projeto antes da configuração.");
    return;
  }

  const setupMode = await vscode.window.showQuickPick(
    [
      { label: "Runtime automático (sem Python)", description: "Recomendado" },
      { label: "Modo Python", description: "Usar Python + run.py" },
    ],
    { placeHolder: "Como você quer configurar o TTT?" }
  );

  if (!setupMode) {
    return;
  }

  if (setupMode.label.startsWith("Runtime automático")) {
    try {
      await runInstallRuntime(context);
      await context.globalState.update("ttt.setupDone", true);
      return;
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      vscode.window.showWarningMessage(`Falha no runtime automático: ${msg}`);
      // fallback para configuração python abaixo
    }
  }

  const python = await detectPythonCommand(workspace.uri.fsPath);
  if (!python) {
    const installChoice = await vscode.window.showWarningMessage(
      "Não encontrei Python instalado. Instale Python 3.9+ e rode 'TTT: Primeira Configuração' novamente.",
      "Abrir download"
    );

    if (installChoice === "Abrir download") {
      void vscode.env.openExternal(vscode.Uri.parse("https://www.python.org/downloads/"));
    }
    return;
  }

  const cfg = vscode.workspace.getConfiguration("ttt", workspace.uri);
  await cfg.update("pythonCommand", python, vscode.ConfigurationTarget.Workspace);
  await cfg.update("runPyPath", "run.py", vscode.ConfigurationTarget.Workspace);

  const installDeps = await vscode.window.showQuickPick(
    [
      { label: "Sim", description: "Instalar dependências automaticamente" },
      { label: "Não", description: "Pular instalação agora" }
    ],
    { placeHolder: "Instalar dependências do TTT agora?" }
  );

  if (installDeps?.label === "Sim") {
    await runInstallDependencies(python, workspace.uri.fsPath);
  }

  const validated = await validateTtt(python, workspace.uri.fsPath);
  if (!validated) {
    vscode.window.showWarningMessage("Configuração concluída, mas validação falhou. Verifique o terminal para detalhes.");
    return;
  }

  await context.globalState.update("ttt.setupDone", true);
  vscode.window.showInformationMessage("TTT configurado com sucesso. Pode usar os comandos TTT no Command Palette.");
}

async function detectPythonCommand(cwd: string): Promise<string | undefined> {
  const candidates = ["py", "python", "python3"];

  for (const cmd of candidates) {
    try {
      await execFileAsync(cmd, ["--version"], { cwd, windowsHide: true });
      return cmd;
    } catch {
      // try next
    }
  }

  return undefined;
}

async function runInstallDependencies(python: string, cwd: string): Promise<void> {
  const terminal = vscode.window.createTerminal("TTT Setup");
  terminal.show(true);
  terminal.sendText(`${python} -m pip install -r \"${path.join(cwd, "requirements.txt")}\"`);
}

async function validateTtt(python: string, cwd: string): Promise<boolean> {
  try {
    const runPy = path.join(cwd, "run.py");
    await execFileAsync(python, [runPy, "--version"], { cwd, windowsHide: true });
    return true;
  } catch {
    return false;
  }
}

async function resolveTttExecutionForWorkspace(workspaceFolder: vscode.WorkspaceFolder) {
  if (!extensionCtx) {
    throw new Error("Extension context not initialized.");
  }
  return resolveTttExecution(extensionCtx, workspaceFolder);
}
