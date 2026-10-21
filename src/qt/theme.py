"""Terminal-style dark theme for the Procoo Qt UI.

All colors are hex strings and all radii are zero (square). This module is the single
source of truth for styling: Python card/markdown builders read the constants directly,
and QML reads them through the :class:`Theme` object exposed as the ``Theme`` context
property (``Theme.colors.pageBg``, ``Theme.metrics.cardRadius``, ``Theme.fontMono``).
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject

# ------------------------------------------------------------------
# Background hierarchy
# ------------------------------------------------------------------
COLOR_PAGE_BG = "#0d1117"
COLOR_SURFACE_BG = "#161b22"
COLOR_ELEVATED_BG = "#1c2128"
COLOR_HOVER_BG = "#21262d"

# ------------------------------------------------------------------
# Text hierarchy
# ------------------------------------------------------------------
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_TEXT_DISABLED = "#484f58"

# ------------------------------------------------------------------
# Accent colors
# ------------------------------------------------------------------
COLOR_ACCENT_CYAN = "#58a6ff"
COLOR_ACCENT_GREEN = "#3fb950"
COLOR_ACCENT_AMBER = "#d29922"
COLOR_ACCENT_RED = "#da3633"
COLOR_ACCENT_MAGENTA = "#bc8cff"
COLOR_ACCENT_BLUE = "#388bfd"

# ------------------------------------------------------------------
# Markdown (terminal-style) palette
# ------------------------------------------------------------------
# Consumed by ``src/qt/markdown.py`` when rendering chat markdown. The single
# exception is ``COLOR_MD_TEXT``, which QML applies to markdown card bodies.
COLOR_MD_TEXT = "#eeeeee"
COLOR_MD_HEADING = "#9d7cd8"
COLOR_MD_BOLD = "#f5a742"
COLOR_MD_ITALIC = "#e5c07b"
COLOR_MD_CODE = "#7fd88f"
COLOR_MD_LINK = "#56b6c2"
COLOR_MD_LIST_MARKER = "#d19a66"
COLOR_MD_LIST_NUMBER = COLOR_MD_LINK
COLOR_MD_QUOTE = "#5c6370"
COLOR_MD_RULE = COLOR_MD_QUOTE
# Glyph colour for LaTeX math, rendered to an in-memory PNG by ``qt.latex``.
COLOR_MD_MATH = COLOR_MD_TEXT

# ------------------------------------------------------------------
# Border colors
# ------------------------------------------------------------------
COLOR_BORDER_DEFAULT = "#30363d"
COLOR_BORDER_LIGHT = "#21262d"
COLOR_BORDER_STRONG = "#484f58"

# ------------------------------------------------------------------
# Button colors
# ------------------------------------------------------------------
COLOR_BUTTON_PRIMARY_BG = COLOR_ACCENT_CYAN
COLOR_BUTTON_PRIMARY_FG = COLOR_PAGE_BG
COLOR_BUTTON_APPROVE_BG = COLOR_ACCENT_GREEN
COLOR_BUTTON_APPROVE_FG = COLOR_PAGE_BG

# ------------------------------------------------------------------
# Chat bubble colors
# ------------------------------------------------------------------
COLOR_BUBBLE_USER = COLOR_PAGE_BG
COLOR_BUBBLE_USER_BORDER = COLOR_ACCENT_GREEN
COLOR_BUBBLE_ASSISTANT = COLOR_PAGE_BG
COLOR_BUBBLE_ASSISTANT_BORDER = COLOR_ACCENT_AMBER

# ------------------------------------------------------------------
# Approval bar
# ------------------------------------------------------------------
COLOR_APPROVAL_BG = "#2b2100"
COLOR_APPROVAL_BORDER = COLOR_ACCENT_AMBER

# ------------------------------------------------------------------
# Context banner
# ------------------------------------------------------------------
COLOR_CONTEXT_BANNER_BG = COLOR_PAGE_BG
COLOR_CONTEXT_BANNER_BORDER = COLOR_BORDER_DEFAULT
COLOR_CONTEXT_BANNER_DELTA_BG = "#2b1a00"
COLOR_CONTEXT_BANNER_DELTA_BORDER = COLOR_ACCENT_AMBER

# ------------------------------------------------------------------
# Chat border
# ------------------------------------------------------------------
COLOR_CHAT_BORDER = COLOR_BORDER_DEFAULT

# ------------------------------------------------------------------
# Error / warning toasts
# ------------------------------------------------------------------
COLOR_ERROR_SNACKBAR = "#490202"
COLOR_WARNING_SNACKBAR = "#3b2900"

# ------------------------------------------------------------------
# Chat status indicators
# ------------------------------------------------------------------
COLOR_CHAT_SELECTED_BG = COLOR_HOVER_BG
COLOR_CHAT_EMPTY = COLOR_TEXT_DISABLED
COLOR_CHAT_FINISHED = COLOR_ACCENT_CYAN
COLOR_CHAT_WAITING = COLOR_ACCENT_AMBER
COLOR_CHAT_ERROR = COLOR_ACCENT_RED
COLOR_CHAT_RUNNING = COLOR_ACCENT_GREEN
COLOR_CHAT_FLASH = "#e6edf3"

# ------------------------------------------------------------------
# Content cards (thinking, tool call, tool result)
# ------------------------------------------------------------------
COLOR_THINKING_BG = COLOR_PAGE_BG
COLOR_THINKING_BORDER = COLOR_ACCENT_BLUE
COLOR_TOOL_CALL_BG = COLOR_PAGE_BG
COLOR_TOOL_CALL_BORDER = COLOR_ACCENT_MAGENTA
COLOR_TOOL_RESULT_BG = COLOR_PAGE_BG
COLOR_TOOL_RESULT_BORDER = COLOR_ACCENT_MAGENTA
COLOR_CARD_HEADER_DIVIDER = COLOR_BORDER_LIGHT

# ------------------------------------------------------------------
# Chip / badge colors (dark bg + colored text)
# ------------------------------------------------------------------
COLOR_CHIP_ACTIVATED_BG = "#1a2b4c"
COLOR_CHIP_ACTIVATED_FG = "#79c0ff"
COLOR_CHIP_TOOLS_BG = COLOR_ELEVATED_BG
COLOR_CHIP_TOOLS_FG = COLOR_TEXT_SECONDARY
COLOR_CHIP_ALLOW_BG = "#1a3b1a"
COLOR_CHIP_ALLOW_FG = COLOR_ACCENT_GREEN
COLOR_CHIP_ASK_BG = "#3b2e00"
COLOR_CHIP_ASK_FG = COLOR_ACCENT_AMBER
COLOR_CHIP_BLOCK_BG = "#3b1a1a"
COLOR_CHIP_BLOCK_FG = COLOR_ACCENT_RED

# Chip foreground variants for the compact config/token number readouts
# (cyan / green / yellow / red chips).
#
COLOR_CHIP_ACTIVATED_FG_MUTED = "#38B2AC"
COLOR_CHIP_ALLOW_FG_MUTED = "#48BB78"
COLOR_CHIP_ASK_FG_MUTED = "#ECC94B"
COLOR_CHIP_BLOCK_FG_MUTED = "#E53E3E"

# ------------------------------------------------------------------
# Tool mode badge colors (shown inside tool call cards)
# ------------------------------------------------------------------
COLOR_TOOL_MODE_ALLOW_BG = "#1a3b1a"
COLOR_TOOL_MODE_ALLOW_FG = COLOR_ACCENT_GREEN
COLOR_TOOL_MODE_ASK_BG = "#3b2e00"
COLOR_TOOL_MODE_ASK_FG = COLOR_ACCENT_AMBER
COLOR_TOOL_MODE_BLOCK_BG = "#3b1a1a"
COLOR_TOOL_MODE_BLOCK_FG = COLOR_ACCENT_RED
COLOR_TOOL_MODE_DEFAULT_BG = COLOR_ELEVATED_BG
COLOR_TOOL_MODE_DEFAULT_FG = COLOR_TEXT_SECONDARY

# ------------------------------------------------------------------
# Automation / notification
# ------------------------------------------------------------------
#: Notification cards keep the page background and signal their nature through
#: the outer border: grey for success logs, amber for info, red for errors.
COLOR_NOTIFICATION_LOG_BORDER = COLOR_TEXT_SECONDARY
COLOR_NOTIFICATION_INFO_BORDER = COLOR_ACCENT_AMBER
COLOR_NOTIFICATION_ERROR_BORDER = COLOR_ACCENT_RED
COLOR_NOTIFICATION_BG = COLOR_PAGE_BG
#: Unread badge colours for the title-bar bell (grey / amber / red).
COLOR_BADGE_LOG_BG = COLOR_TEXT_SECONDARY
COLOR_BADGE_INFO_BG = COLOR_ACCENT_AMBER
COLOR_BADGE_ERROR_BG = COLOR_ACCENT_RED
COLOR_BADGE_FG = COLOR_PAGE_BG
#: Active content tab (Chat / Automation / Notification) underline.
COLOR_CONTENT_TAB_ACTIVE = COLOR_ACCENT_CYAN

# ------------------------------------------------------------------
# Toast overlay
# ------------------------------------------------------------------
COLOR_TOAST_TEXT = COLOR_TEXT_PRIMARY
COLOR_TOAST_SHADOW = COLOR_BORDER_STRONG

# ------------------------------------------------------------------
# Drag feedback
# ------------------------------------------------------------------
COLOR_DRAG_FEEDBACK_BG = COLOR_HOVER_BG
COLOR_DRAG_FEEDBACK_BORDER = COLOR_ACCENT_CYAN
COLOR_DRAG_ICON = COLOR_TEXT_SECONDARY

# ------------------------------------------------------------------
# Split-window drop indicator
# ------------------------------------------------------------------
COLOR_SPLIT_DROP_FILL = "#40e6edf3"
COLOR_SPLIT_DROP_BORDER = COLOR_TEXT_PRIMARY

# ------------------------------------------------------------------
# Resize handle
# ------------------------------------------------------------------
COLOR_RESIZE_HANDLE = COLOR_BORDER_DEFAULT

# ------------------------------------------------------------------
# Text selection (chat card body caret / selection)
# ------------------------------------------------------------------
#: Highlight behind a keyboard/mouse selection in a read-only card body, matching
#: GitHub's dark-theme selection blue; the selected glyphs keep the primary text
#: colour for contrast against it.
COLOR_SELECTION_BG = "#264f78"
COLOR_SELECTION_FG = COLOR_TEXT_PRIMARY

# ------------------------------------------------------------------
# Input fields
# ------------------------------------------------------------------
INPUT_BORDER_COLOR = COLOR_BORDER_STRONG
INPUT_FOCUSED_BORDER_COLOR = COLOR_ACCENT_CYAN
INPUT_FILL_COLOR = COLOR_SURFACE_BG
INPUT_CURSOR_COLOR = COLOR_TEXT_PRIMARY
INPUT_TEXT_COLOR = COLOR_TEXT_PRIMARY

# ------------------------------------------------------------------
# Toggle control metrics (shared checkbox / radio indicator)
# ------------------------------------------------------------------
CONTROL_INDICATOR_SIZE = 12
CONTROL_INDICATOR_RADIUS = 2
CONTROL_DOT_SIZE = 6

# ------------------------------------------------------------------
# Frameless title bar
# ------------------------------------------------------------------
#: Height of the custom window title bar, and the size of its logo and the
#: width of its per-button hit area (minimise / maximise / close).
TITLE_BAR_HEIGHT = 32
TITLE_BAR_LOGO_SIZE = 20
TITLE_BAR_BUTTON_WIDTH = 46

# ------------------------------------------------------------------
# Radius / sizing metrics (all square)
# ------------------------------------------------------------------
BUTTON_RADIUS = 0
CHAT_CONTAINER_RADIUS = 0
APPROVAL_CONTAINER_RADIUS = 0
CARD_RADIUS = 0
CHIP_RADIUS = 0
STATUS_DOT_RADIUS = 2
DROP_ZONE_RADIUS = 0
TOAST_RADIUS = 0
MODE_BADGE_RADIUS = 0
CONFIG_CHIP_RADIUS = 0
CONTEXT_BANNER_RADIUS = 0

ICON_SIZE_SMALL = 14
ICON_SIZE_MEDIUM = 14
ICON_SIZE_LARGE = 18

# Font sizes are point sizes. ``FONT_SIZE_BASE`` is the single size used by all
# non-markdown UI text; ``FONT_SIZE_MARKDOWN`` applies only to chat markdown bodies.
# ``FONT_SIZE_LATEX`` is the point size LaTeX math is rasterised at; it is larger
# than the body text because math glyphs read small at the body size.
FONT_SIZE_GUTTER = 12
FONT_SIZE_TREE = 12
FONT_SIZE_BASE = 12
FONT_SIZE_MARKDOWN = 12
FONT_SIZE_LATEX = 14

#: CSS ``line-height`` for chat card bodies (plain text and markdown), as a
#: percentage of the font size.
LINE_HEIGHT_BODY = "125%"

FONT_MONO = "Sarasa Fixed TC Nerd Font"
FONT_SIZE_BODY = 12
FONT_SIZE_LABEL_SMALL = 12
FONT_SIZE_TITLE_SMALL = 16
FONT_SIZE_TITLE_MEDIUM = 18
FONT_SIZE_TITLE_LARGE = 24

BUTTON_WIDTH_SMALL = 60
BUTTON_WIDTH_MEDIUM = 120
BUTTON_WIDTH_LARGE = 180
BUTTON_WIDTH_SEGMENTED = BUTTON_WIDTH_MEDIUM * 2

#: Distance (logical px) the chat list moves per mouse-wheel notch.
WHEEL_SCROLL_STEP = 120

#: Color registry exposed to QML as ``Theme.colors.<name>``.
COLORS: dict[str, str] = {
    "pageBg": COLOR_PAGE_BG,
    "surfaceBg": COLOR_SURFACE_BG,
    "elevatedBg": COLOR_ELEVATED_BG,
    "hoverBg": COLOR_HOVER_BG,
    "textPrimary": COLOR_TEXT_PRIMARY,
    "textSecondary": COLOR_TEXT_SECONDARY,
    "textDisabled": COLOR_TEXT_DISABLED,
    "mdText": COLOR_MD_TEXT,
    "accentCyan": COLOR_ACCENT_CYAN,
    "accentGreen": COLOR_ACCENT_GREEN,
    "accentAmber": COLOR_ACCENT_AMBER,
    "accentRed": COLOR_ACCENT_RED,
    "accentMagenta": COLOR_ACCENT_MAGENTA,
    "accentBlue": COLOR_ACCENT_BLUE,
    "borderDefault": COLOR_BORDER_DEFAULT,
    "borderLight": COLOR_BORDER_LIGHT,
    "borderStrong": COLOR_BORDER_STRONG,
    "buttonPrimaryBg": COLOR_BUTTON_PRIMARY_BG,
    "buttonPrimaryFg": COLOR_BUTTON_PRIMARY_FG,
    "buttonApproveBg": COLOR_BUTTON_APPROVE_BG,
    "buttonApproveFg": COLOR_BUTTON_APPROVE_FG,
    "bubbleUser": COLOR_BUBBLE_USER,
    "bubbleUserBorder": COLOR_BUBBLE_USER_BORDER,
    "bubbleAssistant": COLOR_BUBBLE_ASSISTANT,
    "bubbleAssistantBorder": COLOR_BUBBLE_ASSISTANT_BORDER,
    "approvalBg": COLOR_APPROVAL_BG,
    "approvalBorder": COLOR_APPROVAL_BORDER,
    "contextBannerBg": COLOR_CONTEXT_BANNER_BG,
    "contextBannerBorder": COLOR_CONTEXT_BANNER_BORDER,
    "contextBannerDeltaBg": COLOR_CONTEXT_BANNER_DELTA_BG,
    "contextBannerDeltaBorder": COLOR_CONTEXT_BANNER_DELTA_BORDER,
    "chatBorder": COLOR_CHAT_BORDER,
    "errorSnackbar": COLOR_ERROR_SNACKBAR,
    "warningSnackbar": COLOR_WARNING_SNACKBAR,
    "chatSelectedBg": COLOR_CHAT_SELECTED_BG,
    "chatEmpty": COLOR_CHAT_EMPTY,
    "chatFinished": COLOR_CHAT_FINISHED,
    "chatWaiting": COLOR_CHAT_WAITING,
    "chatError": COLOR_CHAT_ERROR,
    "chatRunning": COLOR_CHAT_RUNNING,
    "chatFlash": COLOR_CHAT_FLASH,
    "thinkingBg": COLOR_THINKING_BG,
    "thinkingBorder": COLOR_THINKING_BORDER,
    "toolCallBg": COLOR_TOOL_CALL_BG,
    "toolCallBorder": COLOR_TOOL_CALL_BORDER,
    "toolResultBg": COLOR_TOOL_RESULT_BG,
    "toolResultBorder": COLOR_TOOL_RESULT_BORDER,
    "cardHeaderDivider": COLOR_CARD_HEADER_DIVIDER,
    "chipActivatedBg": COLOR_CHIP_ACTIVATED_BG,
    "chipActivatedFg": COLOR_CHIP_ACTIVATED_FG,
    "chipToolsBg": COLOR_CHIP_TOOLS_BG,
    "chipToolsFg": COLOR_CHIP_TOOLS_FG,
    "chipAllowBg": COLOR_CHIP_ALLOW_BG,
    "chipAllowFg": COLOR_CHIP_ALLOW_FG,
    "chipAskBg": COLOR_CHIP_ASK_BG,
    "chipAskFg": COLOR_CHIP_ASK_FG,
    "chipBlockBg": COLOR_CHIP_BLOCK_BG,
    "chipBlockFg": COLOR_CHIP_BLOCK_FG,
    "chipActivatedFgMuted": COLOR_CHIP_ACTIVATED_FG_MUTED,
    "chipAllowFgMuted": COLOR_CHIP_ALLOW_FG_MUTED,
    "chipAskFgMuted": COLOR_CHIP_ASK_FG_MUTED,
    "chipBlockFgMuted": COLOR_CHIP_BLOCK_FG_MUTED,
    "toolModeAllowBg": COLOR_TOOL_MODE_ALLOW_BG,
    "toolModeAllowFg": COLOR_TOOL_MODE_ALLOW_FG,
    "toolModeAskBg": COLOR_TOOL_MODE_ASK_BG,
    "toolModeAskFg": COLOR_TOOL_MODE_ASK_FG,
    "toolModeBlockBg": COLOR_TOOL_MODE_BLOCK_BG,
    "toolModeBlockFg": COLOR_TOOL_MODE_BLOCK_FG,
    "toolModeDefaultBg": COLOR_TOOL_MODE_DEFAULT_BG,
    "toolModeDefaultFg": COLOR_TOOL_MODE_DEFAULT_FG,
    "notificationLogBorder": COLOR_NOTIFICATION_LOG_BORDER,
    "notificationInfoBorder": COLOR_NOTIFICATION_INFO_BORDER,
    "notificationErrorBorder": COLOR_NOTIFICATION_ERROR_BORDER,
    "notificationBg": COLOR_NOTIFICATION_BG,
    "badgeLogBg": COLOR_BADGE_LOG_BG,
    "badgeInfoBg": COLOR_BADGE_INFO_BG,
    "badgeErrorBg": COLOR_BADGE_ERROR_BG,
    "badgeFg": COLOR_BADGE_FG,
    "contentTabActive": COLOR_CONTENT_TAB_ACTIVE,
    "toastText": COLOR_TOAST_TEXT,
    "toastShadow": COLOR_TOAST_SHADOW,
    "dragFeedbackBg": COLOR_DRAG_FEEDBACK_BG,
    "dragFeedbackBorder": COLOR_DRAG_FEEDBACK_BORDER,
    "splitDropFill": COLOR_SPLIT_DROP_FILL,
    "splitDropBorder": COLOR_SPLIT_DROP_BORDER,
    "dragIcon": COLOR_DRAG_ICON,
    "resizeHandle": COLOR_RESIZE_HANDLE,
    "inputBorder": INPUT_BORDER_COLOR,
    "inputFocusedBorder": INPUT_FOCUSED_BORDER_COLOR,
    "inputFill": INPUT_FILL_COLOR,
    "inputCursor": INPUT_CURSOR_COLOR,
    "inputText": INPUT_TEXT_COLOR,
    "selectionBg": COLOR_SELECTION_BG,
    "selectionFg": COLOR_SELECTION_FG,
}

#: Numeric registry exposed to QML as ``Theme.metrics.<name>``.
METRICS: dict[str, int] = {
    "buttonRadius": BUTTON_RADIUS,
    "chatContainerRadius": CHAT_CONTAINER_RADIUS,
    "approvalContainerRadius": APPROVAL_CONTAINER_RADIUS,
    "cardRadius": CARD_RADIUS,
    "chipRadius": CHIP_RADIUS,
    "statusDotRadius": STATUS_DOT_RADIUS,
    "dropZoneRadius": DROP_ZONE_RADIUS,
    "toastRadius": TOAST_RADIUS,
    "modeBadgeRadius": MODE_BADGE_RADIUS,
    "configChipRadius": CONFIG_CHIP_RADIUS,
    "contextBannerRadius": CONTEXT_BANNER_RADIUS,
    "controlIndicatorSize": CONTROL_INDICATOR_SIZE,
    "controlIndicatorRadius": CONTROL_INDICATOR_RADIUS,
    "controlDotSize": CONTROL_DOT_SIZE,
    "iconSizeSmall": ICON_SIZE_SMALL,
    "iconSizeMedium": ICON_SIZE_MEDIUM,
    "iconSizeLarge": ICON_SIZE_LARGE,
    "fontSizeGutter": FONT_SIZE_GUTTER,
    "fontSizeTree": FONT_SIZE_TREE,
    "fontSizeBase": FONT_SIZE_BASE,
    "fontSizeMarkdown": FONT_SIZE_MARKDOWN,
    "fontSizeBody": FONT_SIZE_BODY,
    "fontSizeLabelSmall": FONT_SIZE_LABEL_SMALL,
    "fontSizeTitleSmall": FONT_SIZE_TITLE_SMALL,
    "fontSizeTitleMedium": FONT_SIZE_TITLE_MEDIUM,
    "fontSizeTitleLarge": FONT_SIZE_TITLE_LARGE,
    "buttonWidthSmall": BUTTON_WIDTH_SMALL,
    "buttonWidthMedium": BUTTON_WIDTH_MEDIUM,
    "buttonWidthLarge": BUTTON_WIDTH_LARGE,
    "buttonWidthSegmented": BUTTON_WIDTH_SEGMENTED,
    "wheelScrollStep": WHEEL_SCROLL_STEP,
    "titleBarHeight": TITLE_BAR_HEIGHT,
    "titleBarLogoSize": TITLE_BAR_LOGO_SIZE,
    "titleBarButtonWidth": TITLE_BAR_BUTTON_WIDTH,
}


class Theme(QObject):
    """Read-only theme registry exposed to QML as the ``Theme`` context property.

    Attributes:
        colors: Mapping of QML color name to hex string (``Theme.colors.pageBg``).
        metrics: Mapping of QML metric name to integer (``Theme.metrics.cardRadius``).
        fontMono: The application monospace font family name.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialise the theme object.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(parent)

    # ------------------------------------------------------------------
    #  Properties
    # ------------------------------------------------------------------

    @Property(dict, constant=True)
    def colors(self) -> dict[str, str]:
        """Return the color registry.

        Returns:
            Mapping of QML color name to hex string.
        """
        return COLORS

    @Property(dict, constant=True)
    def metrics(self) -> dict[str, int]:
        """Return the numeric sizing registry.

        Returns:
            Mapping of QML metric name to integer.
        """
        return METRICS

    @Property(str, constant=True)
    def fontMono(self) -> str:  # noqa: N802
        """Return the monospace font family name.

        Returns:
            The font family name.
        """
        return FONT_MONO
