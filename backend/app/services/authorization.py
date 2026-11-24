"""Admin role policy."""

MANAGER_FORBIDDEN_ACTIONS = frozenset({"cars.delete", "settings.write"})


def can_perform_admin_action(role: str, action: str) -> bool:
    """Check permissions for owner and manager roles."""
    if role == "owner":
        return True
    if role != "manager":
        return False
    return action not in MANAGER_FORBIDDEN_ACTIONS
