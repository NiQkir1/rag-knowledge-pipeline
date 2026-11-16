namespace Common.Parsing.Models
{
    public record TextChunk(
        string Content,
        int PageNumber,
        IReadOnlyList<string> HeadingPath,
        SourceAnchor Anchor);
}
