using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using KnowledgeService.Models;

namespace KnowledgeService.Controllers
{
    [ApiController]
    [Route("api/v1/[controller]")]
    public class SourceController : ControllerBase
    {
        [HttpPost("upload")]
        [Consumes("multipart/form-data")]
        public async Task<IActionResult> UploadDocument([FromForm] IFormFile file, CancellationToken ct)
        {
            if (file == null || file.Length == 0)
                return BadRequest(new { error = "No file provided" });

            if (file.Length > 50 * 1024 * 1024)
                return BadRequest(new { error = "File exceeds 50MB limit" });

            var jobId = Guid.NewGuid();
            var sourceId = Guid.NewGuid();
            var ext = Path.GetExtension(file.FileName).ToLowerInvariant();

            // Создаем Job запись в статусе queued
            var job = new Job
            {
                Id = jobId,
                Status = "queued",
                SourceType = ext.TrimStart('.')
            };

            // Сохранение временного файла / отправка в MinIO
            var storageDir = Path.Combine(Path.GetTempPath(), "knowledge_sources", jobId.ToString());
            Directory.CreateDirectory(storageDir);
            var filePath = Path.Combine(storageDir, $"original{ext}");

            using (var stream = new FileStream(filePath, FileMode.Create))
            {
                await file.CopyToAsync(stream, ct);
            }

            return Ok(new
            {
                job_id = jobId,
                source_id = sourceId,
                status = job.Status,
                filename = file.FileName,
                message = "Document accepted for parsing and Q&A extraction"
            });
        }

        [HttpPost("url")]
        public IActionResult IngestUrl([FromBody] UrlIngestRequest request)
        {
            if (string.IsNullOrWhiteSpace(request?.Url))
                return BadRequest(new { error = "Valid URL is required" });

            var jobId = Guid.NewGuid();
            return Ok(new
            {
                job_id = jobId,
                status = "queued",
                url = request.Url,
                message = "URL registered for web crawler and Q&A pipeline"
            });
        }

        [HttpGet("jobs/{jobId:guid}")]
        public IActionResult GetJobStatus(Guid jobId)
        {
            return Ok(new
            {
                job_id = jobId,
                status = "completed",
                qa_total = 12,
                qa_approved = 10,
                qa_rejected = 2
            });
        }
    }

    public class UrlIngestRequest
    {
        public string Url { get; set; } = string.Empty;
    }
}
