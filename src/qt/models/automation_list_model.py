"""``AutomationListModel`` — automation cards for the automation page.

The controller supplies discovered automations plus the current search term; the
model filters them with a fuzzy subsequence match over the name, description,
event, and schedule, then flattens each into a role-keyed row.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..models.base import Item, ListModel
from ..qt_roles import AutomationRole, role_names

if TYPE_CHECKING:
    from ...automation.models import AutomationInfo


def fuzzy_match(query: str, text: str) -> bool:
    """Return whether ``query`` is a case-insensitive subsequence of ``text``.

    Args:
        query: The search term.
        text: The candidate text.

    Returns:
        ``True`` when every character of *query* appears in *text* in order.
    """
    needle = query.strip().casefold()
    if not needle:
        return True
    haystack = text.casefold()
    index = 0
    for char in needle:
        index = haystack.find(char, index)
        if index == -1:
            return False
        index += 1
    return True


class AutomationListModel(ListModel):
    """List model of automation cards, filtered by a fuzzy search term.

    Attributes:
        roles: Automation role mapping (inherited).
    """

    def __init__(self, parent: Any = None) -> None:
        """Initialise the automation model.

        Args:
            parent: Optional Qt parent object.
        """
        super().__init__(role_names(AutomationRole), parent)

    # ------------------------------------------------------------------
    #  Builder
    # ------------------------------------------------------------------

    def set_automations(
        self,
        automations: list[AutomationInfo],
        search: str = "",
        running: set[str] | None = None,
    ) -> None:
        """Replace rows with the automations matching *search*.

        Args:
            automations: Discovered automations.
            search: Fuzzy filter over name/description/event/schedule.
            running: Paths of automations with an in-flight manual run.
        """
        running = running or set()
        rows: list[Item] = []
        keys: list[str] = []
        for info in automations:
            if not self._matches(info, search):
                continue
            rows.append(self._row(info, running))
            keys.append(f"automation:{info.path}")
        self.set_items(rows, keys)

    def set_running(self, path: str, running: bool) -> None:
        """Update a single row's ``RUNNING`` flag without resetting the model.

        Args:
            path: Relative automation path.
            running: Whether the automation currently has an in-flight run.
        """
        try:
            row = self._keys.index(f"automation:{path}")
        except ValueError:
            return
        self.update_item(row, {int(AutomationRole.RUNNING): running})

    # ------------------------------------------------------------------
    #  Private
    # ------------------------------------------------------------------

    @staticmethod
    def _matches(info: AutomationInfo, search: str) -> bool:
        """Return whether an automation matches the search term."""
        if not search.strip():
            return True
        return (
            fuzzy_match(search, info.name)
            or fuzzy_match(search, info.description)
            or fuzzy_match(search, info.event)
            or fuzzy_match(search, info.schedule)
        )

    @staticmethod
    def _row(info: AutomationInfo, running: set[str]) -> Item:
        """Build a role-keyed automation row.

        Args:
            info: The automation to flatten.
            running: Paths of automations with an in-flight manual run.

        Returns:
            A role-keyed row consumed by the QML delegate.
        """
        from ...automation.models import ActivationType

        if info.activation == ActivationType.EVENT:
            schedule_text = f"Event driven ({info.event})"
        else:
            schedule_text = info.schedule
        return {
            int(AutomationRole.PATH): info.path,
            int(AutomationRole.NAME): info.name,
            int(AutomationRole.DESCRIPTION): info.description,
            int(AutomationRole.ACTIVATION): info.activation.value,
            int(AutomationRole.SCHEDULE_TEXT): schedule_text,
            int(AutomationRole.ENABLED): info.enabled,
            int(AutomationRole.LAST_RUN): info.last_run,
            int(AutomationRole.EVENT): info.event,
            int(AutomationRole.RUNNING): info.path in running,
        }
