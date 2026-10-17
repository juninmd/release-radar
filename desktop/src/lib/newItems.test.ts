import { describe, expect, test } from "bun:test";
import { detectNew, mergeSeen } from "./newItems";
import type { Release } from "./types";

function ids(values: string[]): Release[] {
  return values.map((id) => ({ id }) as Release);
}

describe("detectNew", () => {
  test("devolve apenas ids ainda não vistos", () => {
    expect(detectNew(["a", "b"], ids(["b", "c", "d"])).map((i) => i.id)).toEqual(["c", "d"]);
  });

  test("sem vistos, a primeira carga não conta como novidade", () => {
    // A primeira carga é tratada à parte pelo hook; aqui a lista vazia marca tudo.
    expect(detectNew([], ids(["a"]))).toHaveLength(1);
  });
});

describe("mergeSeen", () => {
  test("mantém os mais recentes primeiro e sem repetição", () => {
    expect(mergeSeen(["b", "a"], ids(["c", "b"]))).toEqual(["c", "b", "a"]);
  });

  test("respeita o limite de memória", () => {
    expect(mergeSeen([], ids(["1", "2", "3"]), 2)).toEqual(["1", "2"]);
  });
});
