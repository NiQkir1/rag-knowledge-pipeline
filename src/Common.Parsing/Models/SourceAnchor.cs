using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Common.Parsing.Models
{
    public record SourceAnchor(
    int PageNumber = 0,
    string? Selector = null,
    string? CellReference = null,
    int? CharOffset = null);
}
