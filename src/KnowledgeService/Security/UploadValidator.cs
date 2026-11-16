namespace KnowledgeService.Security;

/// <summary>Белый список расширений + проверка сигнатуры (magic bytes). Клиентскому Content-Type не доверяем.</summary>
public static class UploadValidator
{
    public const int MaxFileBytes = 50 * 1024 * 1024;

    private static readonly Dictionary<string, byte[][]> Signatures = new()
    {
        [".pdf"] = new[] { "%PDF-"u8.ToArray() },
        [".docx"] = new[] { new byte[] { 0x50, 0x4B, 0x03, 0x04 } },
        [".xlsx"] = new[] { new byte[] { 0x50, 0x4B, 0x03, 0x04 } },
    };

    public static bool TryValidate(IFormFile file, out string ext, out string error)
    {
        ext = Path.GetExtension(file.FileName ?? string.Empty).ToLowerInvariant();
        error = string.Empty;

        if (file.Length == 0) { error = "Empty file"; return false; }
        if (file.Length > MaxFileBytes) { error = "File exceeds 50MB limit"; return false; }
        if (!Signatures.TryGetValue(ext, out var sigs)) { error = "Unsupported file type"; return false; }

        Span<byte> head = stackalloc byte[8];
        using var s = file.OpenReadStream();
        var n = s.Read(head);
        var ok = sigs.Any(sig => n >= sig.Length && head[..sig.Length].SequenceEqual(sig));
        if (!ok) error = "File content does not match its extension";
        return ok;
    }
}
