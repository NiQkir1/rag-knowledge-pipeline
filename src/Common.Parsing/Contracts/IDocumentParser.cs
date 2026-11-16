using Common.Parsing.Models;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Common.Parsing.Contracts
{
    public interface IDocumentParser
    {
        bool CanParse(string mimeType);

        Task<ParsedDocument> ParseAsync(
            Stream content,
            string mimeType,
            ParseOptions options,
            CancellationToken cancellationToken = default);
    }
}
