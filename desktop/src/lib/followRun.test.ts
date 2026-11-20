import { describe, expect, test } from "bun:test";
import { followRun, LOST_TRACK, STILL_RUNNING } from "./followRun";
import type { RunSnapshot } from "./types";

const snap = (running: boolean, error: string | null = null): RunSnapshot => ({
  running,
  dry_run: false,
  limit: null,
  started_at: "2026-11-20T10:00:00Z",
  finished_at: running ? null : "2026-11-20T10:05:00Z",
  stats: null,
  error,
});

const noWait = () => Promise.resolve();

function scripted(steps: Array<RunSnapshot | Error>) {
  let i = 0;
  return () => {
    const step = steps[Math.min(i++, steps.length - 1)]!;
    return step instanceof Error ? Promise.reject(step) : Promise.resolve(step);
  };
}

describe("followRun", () => {
  test("para quando o servidor diz que a rodada terminou", async () => {
    const updates: RunSnapshot[] = [];
    const last = await followRun(snap(true), {
      status: scripted([snap(true), snap(false)]),
      onUpdate: (s) => updates.push(s),
      wait: noWait,
    });
    expect(last.running).toBe(false);
    expect(last.error).toBeNull();
    expect(updates).toHaveLength(2);
  });

  test("uma falha isolada de consulta não encerra o acompanhamento", async () => {
    const last = await followRun(snap(true), {
      status: scripted([new Error("network"), snap(true), snap(false)]),
      onUpdate: () => undefined,
      wait: noWait,
    });
    expect(last).toEqual(snap(false));
  });

  test("falhas seguidas param com mensagem de acompanhamento, não de início", async () => {
    const last = await followRun(snap(true), {
      status: scripted([new Error("down")]),
      onUpdate: () => undefined,
      wait: noWait,
      maxConsecutiveErrors: 3,
    });
    expect(last.running).toBe(false);
    expect(last.error).toBe(LOST_TRACK);
  });

  test("desiste após o limite de tentativas com a rodada ainda rodando", async () => {
    const last = await followRun(snap(true), {
      status: scripted([snap(true)]),
      onUpdate: () => undefined,
      wait: noWait,
      maxAttempts: 5,
    });
    expect(last.error).toBe(STILL_RUNNING);
  });
});
