namespace Common.Parsing.Models
{
    public record ParsedDocument(
    IReadOnlyList<TextChunk> Chunks,
    IReadOnlyList<string>? ExtractedLinks = null,
    string? Title = null,
    IReadOnlyDictionary<string, object>? Metadata = null);
}
