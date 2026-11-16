using System;
using System.Text.Json;

namespace KnowledgeService.Models
{
    public class Job
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public string Status { get; set; } = "queued"; 
        // queued -> parsing -> chunking -> indexing -> enriching -> validating -> completed / failed
        public string SourceType { get; set; } = "file";
        public string? ErrorMessage { get; set; }
        public int QaTotal { get; set; } = 0;
        public int QaApproved { get; set; } = 0;
        public int QaRejected { get; set; } = 0;
        public JsonDocument? Options { get; set; }
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    }
}
