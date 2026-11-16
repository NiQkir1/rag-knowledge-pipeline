using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Common.Parsing.Models;

public record ParseOptions(
    int MaxChunkSize = 2000,
    bool ExtractTables = true,
    string? TargetLanguage = null);

