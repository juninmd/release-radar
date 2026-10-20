import type { Skin } from "./types";

/** "system" segue o tema do SO; os demais são fixos. */
export function resolveSkin(skin: Skin, prefersDark: boolean): "dark" | "light" {
  if (skin === "system") return prefersDark ? "dark" : "light";
  return skin;
}

export function applySkin(skin: Skin, root: HTMLElement = document.documentElement): void {
  const prefersDark =
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
      : true;
  root.dataset.skin = resolveSkin(skin, prefersDark);
}
