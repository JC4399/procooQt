// Parsing and building of the Procoo HTML marker.
//
// A linked range is represented as native inline HTML so it survives markdown
// rendering and can carry data:
//
//     <span class="procoo-link procoo-<id>" data-procoo-id="<id>">text</span>
//
// The id is duplicated in a class so the link still resolves even if Obsidian's
// renderer strips the data attribute. The link records only the opaque session
// UUID; the inner text is an arbitrary bookmark.

export const PROCOO_CLASS = "procoo-link";
export const ID_CLASS_PREFIX = "procoo-";

const SPAN_RE = /<span\b[^>]*\bprocoo-link\b[^>]*>[\s\S]*?<\/span>/g;
const ID_ATTR_RE = /data-procoo-id="([^"]+)"/;
const ID_CLASS_RE = /\bprocoo-([0-9a-zA-Z_-]{6,})\b/;

export interface ProcooMarker {
  /** The session UUID. */
  id: string;
  /** Start offset of the whole span in the document. */
  start: number;
  /** End offset (exclusive) of the whole span. */
  end: number;
  /** The inner text without the span tags. */
  inner: string;
}

/** Generate a stable, unique session id. */
export function generateId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === "function") {
    return c.randomUUID();
  }
  return "p-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
}

/** Wrap text in the Procoo marker for a session id. */
export function buildMarker(id: string, text: string): string {
  return (
    `<span class="${PROCOO_CLASS} ${ID_CLASS_PREFIX}${id}" ` +
    `data-procoo-id="${id}">${text}</span>`
  );
}

function extractId(span: string): string | null {
  const attr = ID_ATTR_RE.exec(span);
  if (attr) {
    return attr[1];
  }
  const cls = ID_CLASS_RE.exec(span);
  return cls ? cls[1] : null;
}

/** Return every Procoo marker in a document, in order. */
export function findMarkers(value: string): ProcooMarker[] {
  const markers: ProcooMarker[] = [];
  SPAN_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = SPAN_RE.exec(value)) !== null) {
    const span = match[0];
    const id = extractId(span);
    if (!id) {
      continue;
    }
    const open = span.indexOf(">") + 1;
    const inner = span.slice(open, span.length - "</span>".length);
    markers.push({
      id,
      start: match.index,
      end: match.index + span.length,
      inner,
    });
  }
  return markers;
}

/** Return the marker containing an offset, if any. */
export function markerAt(value: string, offset: number): ProcooMarker | null {
  for (const marker of findMarkers(value)) {
    if (offset >= marker.start && offset <= marker.end) {
      return marker;
    }
  }
  return null;
}

/** Return the first marker overlapping a range, if any. */
export function markerInRange(value: string, from: number, to: number): ProcooMarker | null {
  for (const marker of findMarkers(value)) {
    if (marker.start < to && marker.end > from) {
      return marker;
    }
  }
  return null;
}
