using System;
using System.Text.Json;

namespace KnowledgeService.Models
{
    public class Source
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid JobId { get; set; }
        public string Type { get; set; } = string.Empty; // pdf, docx, web, excel
        public string Uri { get; set; } = string.Empty;
        public string? Title { get; set; }
        public string? Checksum { get; set; }
        public JsonDocument? Metadata { get; set; }
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    }
}
