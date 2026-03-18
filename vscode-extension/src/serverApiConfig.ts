import * as vscode from "vscode";
import * as path from "path";
import { ApiMethodDoc } from "./tfsApi";

export type ServerApiConfig = {
  objects: Record<string, ApiMethodDoc[]>;
  globals: ApiMethodDoc[];
  aliases: Record<string, string>;
};

const EMPTY_CONFIG: ServerApiConfig = {
  objects: {},
  globals: [],
  aliases: {},
};

export async function loadServerApiConfig(workspaceFolder: vscode.WorkspaceFolder): Promise<ServerApiConfig> {
  const config = vscode.workspace.getConfiguration("ttt", workspaceFolder.uri);
  const relativePath = config.get<string>("serverApiConfigPath", ".ttt-server-api.json") as string;

  const configUri = path.isAbsolute(relativePath)
    ? vscode.Uri.file(relativePath)
    : vscode.Uri.joinPath(workspaceFolder.uri, relativePath);

  try {
    const bytes = await vscode.workspace.fs.readFile(configUri);
    const raw = JSON.parse(Buffer.from(bytes).toString("utf-8"));
    return normalize(raw);
  } catch {
    return EMPTY_CONFIG;
  }
}

export function getTemplateConfigContent(): string {
  const template = {
    objects: {
      player: [
        {
          method: "openCustomShop",
          detail: "player:openCustomShop(shopId)",
          description: "Abre a loja custom do seu servidor.",
        },
      ],
      mountSystem: [
        {
          method: "unlock",
          detail: "mountSystem:unlock(player, mountId)",
          description: "Desbloqueia uma montaria custom.",
        },
      ],
    },
    globals: [
      {
        method: "isWeekendDoubleExp",
        detail: "isWeekendDoubleExp() -> boolean",
        description: "Retorna true quando o evento de XP em dobro estiver ativo.",
      },
    ],
    aliases: {
      pl: "player",
      p: "player",
    },
  };

  return `${JSON.stringify(template, null, 2)}\n`;
}

function normalize(input: unknown): ServerApiConfig {
  if (!input || typeof input !== "object") {
    return EMPTY_CONFIG;
  }

  const data = input as {
    objects?: Record<string, unknown[]>;
    globals?: unknown[];
    aliases?: Record<string, unknown>;
  };

  const objects: Record<string, ApiMethodDoc[]> = {};
  for (const [objectName, value] of Object.entries(data.objects ?? {})) {
    const methods = Array.isArray(value)
      ? value
          .map(toApiMethod)
          .filter((m): m is ApiMethodDoc => Boolean(m))
      : [];

    objects[objectName.toLowerCase()] = methods;
  }

  const globals = (Array.isArray(data.globals) ? data.globals : [])
    .map(toApiMethod)
    .filter((m): m is ApiMethodDoc => Boolean(m));

  const aliases: Record<string, string> = {};
  for (const [key, value] of Object.entries(data.aliases ?? {})) {
    if (typeof value === "string" && value.trim()) {
      aliases[key.toLowerCase()] = value.toLowerCase();
    }
  }

  return { objects, globals, aliases };
}

function toApiMethod(input: unknown): ApiMethodDoc | undefined {
  if (!input || typeof input !== "object") {
    return undefined;
  }

  const data = input as Partial<ApiMethodDoc>;
  if (!data.method || !data.detail || !data.description) {
    return undefined;
  }

  return {
    method: String(data.method),
    detail: String(data.detail),
    description: String(data.description),
  };
}
