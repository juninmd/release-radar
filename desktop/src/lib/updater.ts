import { isTauri } from "./api";

export interface UpdateInfo {
  available: boolean;
  version?: string;
  notes?: string;
}

/** Versão instalada do app (só existe dentro do Tauri). */
export async function currentVersion(): Promise<string | null> {
  if (!isTauri()) return null;
  const { getVersion } = await import("@tauri-apps/api/app");
  return getVersion();
}

export async function checkForUpdate(): Promise<UpdateInfo> {
  if (!isTauri()) return { available: false };
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) return { available: false };
  return { available: true, version: update.version, notes: update.body ?? "" };
}

/** Baixa, instala e reinicia. Só instala pacote assinado pela chave do projeto. */
export async function installUpdate(): Promise<void> {
  if (!isTauri()) return;
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) return;
  await update.downloadAndInstall();
  const { relaunch } = await import("@tauri-apps/plugin-process");
  await relaunch();
}
