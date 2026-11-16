using System.Security.Claims;

namespace KnowledgeService.Security;

public static class UserContext
{
    public static string TenantId(this ClaimsPrincipal u) => u.FindFirstValue("tenant_id") ?? "default";

    public static HashSet<string> Roles(this ClaimsPrincipal u) =>
        u.FindAll(ClaimTypes.Role).Select(c => c.Value).ToHashSet(StringComparer.OrdinalIgnoreCase);
}
