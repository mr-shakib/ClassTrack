/**
 * Search where a teacher's initial is an exact key.
 *
 * Initials are unique, so a query that *is* someone's initial means that one
 * teacher -- "AA" must not also bring up AAM and AAA. Anything else (a partial
 * initial while typing, a name, a course, a room) matches as a substring.
 *
 * `initials` is every initial the list being searched contains.
 */
export function teacherMatcher(query: string, initials: Iterable<string>) {
  const q = query.trim().toUpperCase();
  if (!q) return () => true;

  const known = new Set<string>();
  for (const i of initials) known.add(i.toUpperCase());

  if (known.has(q)) {
    return (initial: string) => initial.toUpperCase() === q;
  }
  return (initial: string, ...fields: (string | null | undefined)[]) =>
    [initial, ...fields].some((f) => (f ?? "").toUpperCase().includes(q));
}
