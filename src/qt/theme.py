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
COLOR_BUBBLE_USER = "#000000"
COLOR_BUBBLE_USER_BORDER = COLOR_ACCENT_GREEN
COLOR_BUBBLE_ASSISTANT = "#000000"
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
# Session status indicators
# ------------------------------------------------------------------
COLOR_SESSION_SELECTED_BG = COLOR_HOVER_BG
COLOR_SESSION_EMPTY = COLOR_TEXT_DISABLED
COLOR_SESSION_FINISHED = COLOR_ACCENT_CYAN
COLOR_SESSION_WAITING = COLOR_ACCENT_AMBER
COLOR_SESSION_ERROR = COLOR_ACCENT_RED
COLOR_SESSION_RUNNING = COLOR_ACCENT_GREEN
COLOR_SESSION_FLASH = "#e6edf3"

# ------------------------------------------------------------------
# Content cards (thinking, tool call, tool result)
# ------------------------------------------------------------------
COLOR_THINKING_BG = "#000000"
COLOR_THINKING_BORDER = COLOR_ACCENT_BLUE
COLOR_TOOL_CALL_BG = "#000000"
COLOR_TOOL_CALL_BORDER = COLOR_ACCENT_MAGENTA
COLOR_TOOL_RESULT_BG = "#000000"
COLOR_TOOL_RESULT_BORDER = COLOR_ACCENT_MAGENTA
COLOR_CARD_HEADER_DIVIDER = COLOR_BORDER_LIGHT

# ------------------------------------------------------------------
# Chip / badge colors (dark bg + colored text)
# ------------------------------------------------------------------
COLOR_CHIP_PRIMARY_BG = "#1a2b4c"
COLOR_CHIP_PRIMARY_FG = "#79c0ff"
COLOR_CHIP_SECONDARY_BG = COLOR_ELEVATED_BG
COLOR_CHIP_SECONDARY_FG = COLOR_TEXT_SECONDARY
COLOR_CHIP_ALLOW_BG = "#1a3b1a"
COLOR_CHIP_ALLOW_FG = COLOR_ACCENT_GREEN
COLOR_CHIP_ASK_BG = "#3b2e00"
COLOR_CHIP_ASK_FG = COLOR_ACCENT_AMBER
COLOR_CHIP_BLOCK_BG = "#3b1a1a"
COLOR_CHIP_BLOCK_FG = COLOR_ACCENT_RED

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
# Resize handle
# ------------------------------------------------------------------
COLOR_RESIZE_HANDLE = COLOR_BORDER_DEFAULT

# ------------------------------------------------------------------
# Input fields
# ------------------------------------------------------------------
INPUT_BORDER_COLOR = COLOR_BORDER_STRONG
INPUT_FOCUSED_BORDER_COLOR = COLOR_ACCENT_CYAN
INPUT_FILL_COLOR = COLOR_SURFACE_BG
INPUT_CURSOR_COLOR = COLOR_TEXT_PRIMARY
INPUT_TEXT_COLOR = COLOR_TEXT_PRIMARY

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

FONT_SIZE_GUTTER = 12
FONT_SIZE_TREE = 14

FONT_MONO = "Sarasa Fixed TC"
FONT_SIZE_BODY = 14
FONT_SIZE_LABEL_SMALL = 13
FONT_SIZE_TITLE_SMALL = 16
FONT_SIZE_TITLE_MEDIUM = 18
FONT_SIZE_TITLE_LARGE = 24

BUTTON_WIDTH_SMALL = 60
BUTTON_WIDTH_MEDIUM = 120
BUTTON_WIDTH_LARGE = 180
BUTTON_WIDTH_SEGMENTED = BUTTON_WIDTH_MEDIUM * 2

#: Color registry exposed to QML as ``Theme.colors.<name>``.
COLORS: dict[str, str] = {
    "pageBg": COLOR_PAGE_BG,
    "surfaceBg": COLOR_SURFACE_BG,
    "elevatedBg": COLOR_ELEVATED_BG,
    "hoverBg": COLOR_HOVER_BG,
    "textPrimary": COLOR_TEXT_PRIMARY,
    "textSecondary": COLOR_TEXT_SECONDARY,
    "textDisabled": COLOR_TEXT_DISABLED,
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
    "sessionSelectedBg": COLOR_SESSION_SELECTED_BG,
    "sessionEmpty": COLOR_SESSION_EMPTY,
    "sessionFinished": COLOR_SESSION_FINISHED,
    "sessionWaiting": COLOR_SESSION_WAITING,
    "sessionError": COLOR_SESSION_ERROR,
    "sessionRunning": COLOR_SESSION_RUNNING,
    "sessionFlash": COLOR_SESSION_FLASH,
    "thinkingBg": COLOR_THINKING_BG,
    "thinkingBorder": COLOR_THINKING_BORDER,
    "toolCallBg": COLOR_TOOL_CALL_BG,
    "toolCallBorder": COLOR_TOOL_CALL_BORDER,
    "toolResultBg": COLOR_TOOL_RESULT_BG,
    "toolResultBorder": COLOR_TOOL_RESULT_BORDER,
    "cardHeaderDivider": COLOR_CARD_HEADER_DIVIDER,
    "chipPrimaryBg": COLOR_CHIP_PRIMARY_BG,
    "chipPrimaryFg": COLOR_CHIP_PRIMARY_FG,
    "chipSecondaryBg": COLOR_CHIP_SECONDARY_BG,
    "chipSecondaryFg": COLOR_CHIP_SECONDARY_FG,
    "chipAllowBg": COLOR_CHIP_ALLOW_BG,
    "chipAllowFg": COLOR_CHIP_ALLOW_FG,
    "chipAskBg": COLOR_CHIP_ASK_BG,
    "chipAskFg": COLOR_CHIP_ASK_FG,
    "chipBlockBg": COLOR_CHIP_BLOCK_BG,
    "chipBlockFg": COLOR_CHIP_BLOCK_FG,
    "toolModeAllowBg": COLOR_TOOL_MODE_ALLOW_BG,
    "toolModeAllowFg": COLOR_TOOL_MODE_ALLOW_FG,
    "toolModeAskBg": COLOR_TOOL_MODE_ASK_BG,
    "toolModeAskFg": COLOR_TOOL_MODE_ASK_FG,
    "toolModeBlockBg": COLOR_TOOL_MODE_BLOCK_BG,
    "toolModeBlockFg": COLOR_TOOL_MODE_BLOCK_FG,
    "toolModeDefaultBg": COLOR_TOOL_MODE_DEFAULT_BG,
    "toolModeDefaultFg": COLOR_TOOL_MODE_DEFAULT_FG,
    "toastText": COLOR_TOAST_TEXT,
    "toastShadow": COLOR_TOAST_SHADOW,
    "dragFeedbackBg": COLOR_DRAG_FEEDBACK_BG,
    "dragFeedbackBorder": COLOR_DRAG_FEEDBACK_BORDER,
    "dragIcon": COLOR_DRAG_ICON,
    "resizeHandle": COLOR_RESIZE_HANDLE,
    "inputBorder": INPUT_BORDER_COLOR,
    "inputFocusedBorder": INPUT_FOCUSED_BORDER_COLOR,
    "inputFill": INPUT_FILL_COLOR,
    "inputCursor": INPUT_CURSOR_COLOR,
    "inputText": INPUT_TEXT_COLOR,
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
    "iconSizeSmall": ICON_SIZE_SMALL,
    "iconSizeMedium": ICON_SIZE_MEDIUM,
    "iconSizeLarge": ICON_SIZE_LARGE,
    "fontSizeGutter": FONT_SIZE_GUTTER,
    "fontSizeTree": FONT_SIZE_TREE,
    "fontSizeBody": FONT_SIZE_BODY,
    "fontSizeLabelSmall": FONT_SIZE_LABEL_SMALL,
    "fontSizeTitleSmall": FONT_SIZE_TITLE_SMALL,
    "fontSizeTitleMedium": FONT_SIZE_TITLE_MEDIUM,
    "fontSizeTitleLarge": FONT_SIZE_TITLE_LARGE,
    "buttonWidthSmall": BUTTON_WIDTH_SMALL,
    "buttonWidthMedium": BUTTON_WIDTH_MEDIUM,
    "buttonWidthLarge": BUTTON_WIDTH_LARGE,
    "buttonWidthSegmented": BUTTON_WIDTH_SEGMENTED,
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
