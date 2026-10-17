import { describe, expect, test } from "bun:test";
import {
  normalize,
  normalizeShortcut,
  prettyShortcut,
  releaseWindow,
  relativeTime,
  safeUrl,
  shortTime,
} from "./format";

describe("normalize", () => {
  test("ignora acentos e caixa", () => {
    expect(normalize("Séries ANIMADAS")).toBe("series animadas");
    expect(normalize(undefined)).toBe("");
  });
});

describe("safeUrl", () => {
  test("aceita http e https sem credenciais", () => {
    expect(safeUrl("https://example.test/a")).toBe("https://example.test/a");
    expect(safeUrl("http://example.test")).toBe("http://example.test/");
  });

  test("recusa esquemas perigosos e credenciais embutidas", () => {
    expect(safeUrl("javascript:alert(1)")).toBeNull();
    expect(safeUrl("https://user:pass@example.test")).toBeNull();
    expect(safeUrl(null)).toBeNull();
    expect(safeUrl("não é url")).toBeNull();
  });
});

describe("releaseWindow", () => {
  test("formata datas ISO em pt-BR", () => {
    expect(releaseWindow({ release_date: "2026-12-25" })).toBe("25 de dez. de 2026");
  });

  test("usa a janela textual quando não há data ISO", () => {
    expect(releaseWindow({ release_window: "Segundo semestre" })).toBe("Segundo semestre");
    expect(releaseWindow({ release_window: "A definir" })).toBe("Data a confirmar");
    expect(releaseWindow({})).toBe("Data a confirmar");
  });

  test("descarta datas inválidas mantendo o texto", () => {
    expect(releaseWindow({ release_date: "2026-02-31" })).toBe("2026-02-31");
  });
});

describe("relativeTime", () => {
  test("descreve minutos, horas e dias", () => {
    const now = Date.now();
    expect(relativeTime(new Date(now - 30_000).toISOString())).toBe("agora");
    expect(relativeTime(new Date(now - 5 * 60_000).toISOString())).toBe("há 5 min");
    expect(relativeTime(new Date(now - 3 * 3_600_000).toISOString())).toBe("há 3 h");
    expect(relativeTime(new Date(now - 2 * 86_400_000).toISOString())).toBe("há 2 d");
    expect(relativeTime(null)).toBe("");
  });
});

describe("shortTime", () => {
  test("ignora valores vazios ou inválidos", () => {
    expect(shortTime(null)).toBe("");
    expect(shortTime("nada")).toBe("");
    expect(shortTime(new Date("2026-01-02T13:05:00Z"))).not.toBe("");
  });
});

describe("prettyShortcut / normalizeShortcut", () => {
  test("deixa o atalho legível", () => {
    expect(prettyShortcut("ctrl+alt+r")).toBe("Ctrl+Alt+R");
    expect(prettyShortcut("control+shift+space")).toBe("Ctrl+Shift+Space");
    expect(prettyShortcut("ctrl+alt+f5")).toBe("Ctrl+Alt+F5");
    expect(prettyShortcut(null)).toBe("");
  });

  test("normaliza o que o usuário digita", () => {
    expect(normalizeShortcut(" Ctrl + Shift + R ")).toBe("ctrl+shift+r");
    expect(normalizeShortcut("")).toBe("");
  });
});
