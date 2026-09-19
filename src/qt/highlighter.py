"""``QSyntaxHighlighter`` for the QML code editor.

Attaches to a QML ``TextArea``'s ``QQuickTextDocument`` (see
:meth:`~src.qt.editor_controller.EditorController.attachHighlighter`). Rule sets are
selected per language via :meth:`CodeHighlighter.set_language`; Python/YAML/JSON/Bash/
Markdown have dedicated rules while other languages fall back to a generic set. Every
rule covers keywords, numbers, strings, and comments, reusing the :mod:`theme` colors.
"""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from .theme import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_CYAN,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_MAGENTA,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)

# ------------------------------------------------------------------
#  Keyword sets
# ------------------------------------------------------------------
_PYTHON_KEYWORDS = (
    "and",
    "as",
    "assert",
    "async",
    "await",
    "break",
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "None",
    "nonlocal",
    "not",
    "or",
    "pass",
    "raise",
    "return",
    "True",
    "False",
    "try",
    "while",
    "with",
    "yield",
)

_JAVASCRIPT_KEYWORDS = (
    "async",
    "await",
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "null",
    "of",
    "return",
    "switch",
    "this",
    "throw",
    "true",
    "false",
    "try",
    "typeof",
    "undefined",
    "var",
    "void",
    "while",
    "yield",
)

_BASH_KEYWORDS = (
    "alias",
    "case",
    "cd",
    "do",
    "done",
    "echo",
    "elif",
    "else",
    "esac",
    "exit",
    "export",
    "fi",
    "for",
    "function",
    "if",
    "in",
    "local",
    "read",
    "return",
    "select",
    "set",
    "source",
    "then",
    "time",
    "unset",
    "until",
    "while",
)

_SQL_KEYWORDS = (
    "ADD",
    "ALTER",
    "AND",
    "AS",
    "ASC",
    "BY",
    "CREATE",
    "DELETE",
    "DESC",
    "DROP",
    "FROM",
    "GROUP",
    "HAVING",
    "INDEX",
    "INSERT",
    "INTO",
    "JOIN",
    "LEFT",
    "LIMIT",
    "NOT",
    "NULL",
    "ON",
    "OR",
    "ORDER",
    "PRIMARY",
    "RIGHT",
    "SELECT",
    "SET",
    "TABLE",
    "UPDATE",
    "VALUES",
    "WHERE",
)

_KEYWORD_SETS: dict[str, tuple[str, ...]] = {
    "python": _PYTHON_KEYWORDS,
    "yaml": ("true", "false", "null", "yes", "no", "on", "off"),
    "json": ("true", "false", "null"),
    "bash": _BASH_KEYWORDS,
    "javascript": _JAVASCRIPT_KEYWORDS,
    "sql": _SQL_KEYWORDS,
    "html": (),
    "css": (),
    "markdown": (),
    "plain": (),
}

#: Single-line comment token per language (``None`` when there is none).
_COMMENT_TOKENS: dict[str, str] = {
    "python": "#",
    "yaml": "#",
    "bash": "#",
    "javascript": "//",
    "sql": "--",
}

#: Languages with a dedicated rule set; anything else normalises to ``"plain"``.
SUPPORTED_LANGUAGES = frozenset(_KEYWORD_SETS)


def _format(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    """Build a character format.

    Args:
        color: Foreground hex color.
        bold: Whether to bold the text.
        italic: Whether to italicise the text.

    Returns:
        The configured character format.
    """
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Weight.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


def _keyword_pattern(keywords: tuple[str, ...]) -> QRegularExpression | None:
    """Compile a word-boundary alternation over ``keywords``.

    Args:
        keywords: The keywords for a language.

    Returns:
        The compiled pattern, or ``None`` when there are no keywords.
    """
    if not keywords:
        return None
    joined = "|".join(keywords)
    return QRegularExpression(rf"\b(?:{joined})\b")


class CodeHighlighter(QSyntaxHighlighter):
    """Multi-language syntax highlighter with selectable rule sets.

    Attributes:
        rules: Compiled ``(pattern, format)`` highlight rules.
        language: The active language name.
    """

    def __init__(self, document: QTextDocument) -> None:
        """Initialise the highlighter.

        Args:
            document: The text document to highlight.
        """
        super().__init__(document)
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = []
        self.language = "plain"
        self._comment_token: str | None = None
        self._build_rules()

    # ------------------------------------------------------------------
    #  Public
    # ------------------------------------------------------------------

    def set_language(self, language: str) -> None:
        """Swap in the rule set for ``language`` and re-highlight the document.

        Unknown languages fall back to a generic set under the name ``"plain"``.

        Args:
            language: One of the supported language names.
        """
        normalised = language if language in SUPPORTED_LANGUAGES else "plain"
        if normalised == self.language:
            return
        self.language = normalised
        self._build_rules()
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        """Apply the active rules to one block of text.

        Args:
            text: The line of text to highlight.
        """
        for pattern, fmt in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        if self._comment_token:
            index = text.find(self._comment_token)
            if index >= 0:
                fmt = _format(COLOR_TEXT_SECONDARY, italic=True)
                self.setFormat(index, len(text) - index, fmt)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def _build_rules(self) -> None:
        """Compile the rule set for the active language."""
        self.rules = []
        self._comment_token = _COMMENT_TOKENS.get(self.language)
        self.rules.extend(self._keyword_rules())
        self.rules.extend(self._literal_rules())
        self.rules.extend(self._extra_rules())

    def _keyword_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        """Build the keyword rule for the active language.

        Returns:
            A single-rule list, or an empty list when there are no keywords.
        """
        pattern = _keyword_pattern(_KEYWORD_SETS.get(self.language, ()))
        if pattern is None:
            return []
        return [(pattern, _format(COLOR_ACCENT_MAGENTA, bold=True))]

    @staticmethod
    def _literal_rules() -> list[tuple[QRegularExpression, QTextCharFormat]]:
        """Build the shared number and string rules.

        Returns:
            The number and string rules.
        """
        number_fmt = _format(COLOR_ACCENT_CYAN)
        string_fmt = _format(COLOR_ACCENT_GREEN)
        return [
            (QRegularExpression(r"\b[0-9]+(\.[0-9]+)?\b"), number_fmt),
            (QRegularExpression(r"\"[^\"]*\"|'[^']*'"), string_fmt),
        ]

    def _extra_rules(self) -> list[tuple[QRegularExpression, QTextCharFormat]]:
        """Build the language-specific extra rules.

        Returns:
            Clause rules for Markdown, tags for HTML, or properties for CSS.
        """
        if self.language == "markdown":
            heading_fmt = _format(COLOR_ACCENT_CYAN, bold=True)
            bold_fmt = _format(COLOR_ACCENT_MAGENTA, bold=True)
            code_fmt = _format(COLOR_ACCENT_GREEN)
            link_fmt = _format(COLOR_ACCENT_BLUE)
            return [
                (QRegularExpression(r"^#{1,6} .*"), heading_fmt),
                (QRegularExpression(r"\*\*[^*]+\*\*"), bold_fmt),
                (QRegularExpression(r"`[^`]+`"), code_fmt),
                (QRegularExpression(r"\[[^\]]*\]\([^)]*\)"), link_fmt),
            ]
        if self.language == "html":
            return [(QRegularExpression(r"</?[A-Za-z][^>]*>"), _format(COLOR_ACCENT_BLUE))]
        if self.language == "css":
            return [(QRegularExpression(r"[a-z-]+(?=\s*:)"), _format(COLOR_ACCENT_CYAN))]
        if self.language == "plain":
            return [(QRegularExpression(r"^\s*[-:]\S*"), _format(COLOR_TEXT_PRIMARY))]
        return []
