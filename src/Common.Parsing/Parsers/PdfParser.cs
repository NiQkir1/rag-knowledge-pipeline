using Common.Parsing.Contracts;
using Common.Parsing.Models;
using UglyToad.PdfPig;
using UglyToad.PdfPig.Content;

namespace Common.Parsing.Parsers;

public class PdfParser : IDocumentParser
{
    public bool CanParse(string mimeType) =>
        mimeType is "application/pdf" or ".pdf";

    public async Task<ParsedDocument> ParseAsync(
        Stream content,
        string mimeType,
        ParseOptions options,
        CancellationToken cancellationToken = default)
    {
        using var document = PdfDocument.Open(content);
        var chunks = new List<TextChunk>();

        foreach (var page in document.GetPages())
        {
            cancellationToken.ThrowIfCancellationRequested();
            var text = page.Text.Trim();
            if (string.IsNullOrWhiteSpace(text)) continue;

                chunks.Add(new TextChunk(
                Content: text,
                PageNumber: page.Number,
                HeadingPath: Array.Empty<string>(),
                Anchor: new SourceAnchor(PageNumber: page.Number)
            ));
        }

        return new ParsedDocument(chunks.AsReadOnly());
    }
}