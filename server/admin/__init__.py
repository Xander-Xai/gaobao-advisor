"""运营后台：管理员鉴权、数据查询、质检任务与审计。"""

from server.admin.auth import (
    AdminConfigError,
    AdminPrincipal,
    ensure_admin_ready,
    get_admin_config,
)

__all__ = ["AdminConfigError", "AdminPrincipal", "ensure_admin_ready", "get_admin_config"]
