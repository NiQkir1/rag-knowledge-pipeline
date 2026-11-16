using System.Net;
using System.Net.Sockets;

namespace KnowledgeService.Security;

/// <summary>Защита от SSRF: только http/https, блокировка приватных/loopback/link-local адресов.
/// Проверка выполняется на этапе подключения (после DNS-резолва), что закрывает DNS-rebinding.</summary>
public static class SsrfGuard
{
    public static bool TryValidateUrl(string? raw, out Uri? uri, out string error)
    {
        uri = null; error = string.Empty;
        if (!Uri.TryCreate(raw, UriKind.Absolute, out var u)) { error = "Invalid URL"; return false; }
        if (u.Scheme is not ("http" or "https")) { error = "Only http/https allowed"; return false; }
        if (!string.IsNullOrEmpty(u.UserInfo)) { error = "Credentials in URL not allowed"; return false; }
        if (IPAddress.TryParse(u.Host, out var ip) && IsBlocked(ip)) { error = "Target address not allowed"; return false; }
        uri = u;
        return true;
    }

    public static bool IsBlocked(IPAddress ip)
    {
        if (ip.IsIPv4MappedToIPv6) ip = ip.MapToIPv4();
        if (IPAddress.IsLoopback(ip) || ip.Equals(IPAddress.Any) || ip.Equals(IPAddress.IPv6Any)) return true;

        if (ip.AddressFamily == AddressFamily.InterNetworkV6)
            return ip.IsIPv6LinkLocal || ip.IsIPv6SiteLocal || ip.IsIPv6Multicast || (ip.GetAddressBytes()[0] & 0xFE) == 0xFC;

        var b = ip.GetAddressBytes();
        return b[0] == 10
            || (b[0] == 172 && b[1] is >= 16 and <= 31)
            || (b[0] == 192 && b[1] == 168)
            || (b[0] == 169 && b[1] == 254)          // link-local / cloud metadata
            || (b[0] == 100 && b[1] is >= 64 and <= 127) // CGNAT
            || b[0] == 0 || b[0] >= 224;
    }

    public static async ValueTask<Stream> SafeConnectAsync(SocketsHttpConnectionContext ctx, CancellationToken ct)
    {
        var addrs = await Dns.GetHostAddressesAsync(ctx.DnsEndPoint.Host, ct);
        var allowed = addrs.Where(a => !IsBlocked(a)).ToArray();
        if (allowed.Length == 0) throw new HttpRequestException("Target address not allowed");

        var socket = new Socket(SocketType.Stream, ProtocolType.Tcp) { NoDelay = true };
        try
        {
            await socket.ConnectAsync(allowed, ctx.DnsEndPoint.Port, ct);
            return new NetworkStream(socket, ownsSocket: true);
        }
        catch { socket.Dispose(); throw; }
    }
}
