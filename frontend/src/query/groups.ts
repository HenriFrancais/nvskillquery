// Share-URL handling for the pool filter (&g=Home,Strat). The query tree and
// the pool are separate: the tree says what skills to require, the pool says
// which characters are considered at all.

/**
 * Selection -> `g` param value. Null when the param should be omitted:
 * all groups selected (the default) or nothing selected (not shareable —
 * the Run button is disabled in that state).
 */
export function groupsToParam(selected: Set<string>, all: string[]): string | null {
  if (selected.size === 0 || selected.size >= all.length) return null
  // Vocabulary order keeps URLs stable regardless of click order.
  return all.filter((g) => selected.has(g)).join(',')
}

/** `g` param value -> selection. Absent/invalid names fall back to all. */
export function parseGroupsParam(param: string | null, all: string[]): Set<string> {
  if (!param) return new Set(all)
  const known = new Set(all)
  const picked = param.split(',').filter((g) => known.has(g))
  return picked.length > 0 ? new Set(picked) : new Set(all)
}
