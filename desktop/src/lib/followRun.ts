import type { RunSnapshot } from "./types";

export interface FollowRunOptions {
  /** Consulta o estado da rodada no servidor. */
  status: () => Promise<RunSnapshot>;
  /** Recebe cada snapshot (inclusive o final). */
  onUpdate: (snapshot: RunSnapshot) => void;
  wait?: (ms: number) => Promise<void>;
  intervalMs?: number;
  /** ~30 min com o intervalo padrão: depois disso desiste de acompanhar. */
  maxAttempts?: number;
  /** Falhas seguidas toleradas antes de parar (rede oscilando não é rodada que falhou). */
  maxConsecutiveErrors?: number;
}

export const STILL_RUNNING = "A rodada continua no servidor; atualize em alguns minutos.";
export const LOST_TRACK = "Não foi possível acompanhar a rodada; ela pode continuar no servidor.";

const sleep = (ms: number) => new Promise<void>((resolve) => window.setTimeout(resolve, ms));

/** Acompanha uma rodada já iniciada até terminar, sem confundir falha de consulta com falha da rodada. */
export async function followRun(started: RunSnapshot, options: FollowRunOptions): Promise<RunSnapshot> {
  const { status, onUpdate, wait = sleep, intervalMs = 2000, maxAttempts = 900, maxConsecutiveErrors = 3 } = options;
  let last = started;
  let errors = 0;
  for (let attempt = 0; attempt < maxAttempts && last.running; attempt += 1) {
    await wait(intervalMs);
    try {
      last = await status();
      errors = 0;
      onUpdate(last);
    } catch {
      errors += 1;
      if (errors >= maxConsecutiveErrors) {
        last = { ...last, running: false, error: LOST_TRACK };
        onUpdate(last);
        return last;
      }
    }
  }
  if (last.running) {
    last = { ...last, running: false, error: STILL_RUNNING };
    onUpdate(last);
  }
  return last;
}
