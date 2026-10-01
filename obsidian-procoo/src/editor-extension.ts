import { RangeSetBuilder } from "@codemirror/state";
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { findMarkers } from "./markup";

// Live-preview rendering of Procoo markers: the <span ...> and </span> tags are
// hidden and the inner text is given a `.procoo-mark` background. Reading-view
// rendering is handled separately by a markdown post-processor in main.ts.

const hiddenTag = Decoration.replace({});
const markedText = Decoration.mark({ class: "procoo-mark" });

function buildDecorations(view: EditorView): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();
  const value = view.state.doc.toString();
  const closeLen = "</span>".length;

  for (const marker of findMarkers(value)) {
    const span = value.slice(marker.start, marker.end);
    const openEnd = marker.start + span.indexOf(">") + 1;
    const closeStart = marker.end - closeLen;

    if (openEnd > marker.start) {
      builder.add(marker.start, openEnd, hiddenTag);
    }
    if (closeStart > openEnd) {
      builder.add(openEnd, closeStart, markedText);
    }
    if (marker.end > closeStart) {
      builder.add(closeStart, marker.end, hiddenTag);
    }
  }
  return builder.finish();
}

export const procooEditorExtension = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildDecorations(view);
    }

    update(update: ViewUpdate): void {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  {
    decorations: (plugin) => plugin.decorations,
  },
);
