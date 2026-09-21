import QtQuick

// Pre-response placeholder: a headerless grey KnightRiderSpinner shown at the
// end of the chat list while a generation is busy but the assistant turn has
// produced nothing yet (prefill, slow network, or a pending failure). CardBase
// renders the spinner for a pending card with no body; the first streamed card
// replaces this row through the render-plan diff.
CardBase {
    kind: "waiting"
    headerVisible: false
    accentColor: Theme.colors.textSecondary
    borderAllSides: false
}
