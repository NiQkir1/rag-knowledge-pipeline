using KnowledgeService.Models;
using KnowledgeService.Security;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace KnowledgeService.Controllers
{
    [ApiController]
    [Authorize(Policy = "Ingest")]
    [Route("api/v1/[controller]")]
    public class SourceController : ControllerBase
    {
        private readonly IHttpClientFactory _http;
        public SourceController(IHttpClientFactory http) => _http = http;

        [HttpPost("upload")]
        [Consumes("multipart/form-data")]
        [RequestSizeLimit(UploadValidator.MaxFileBytes + 1024 * 1024)]
        public async Task<IActionResult> UploadDocument([FromForm] IFormFile file, CancellationToken ct)
        {
            if (file is null) return BadRequest(new { error = "No file provided" });
            if (!UploadValidator.TryValidate(file, out var ext, out var error))
                return BadRequest(new { error });

            var jobId = Guid.NewGuid();
            var sourceId = Guid.NewGuid();

            // Имя файла на диске генерируется сервером; пользовательское имя не используется в путях.
            var storageDir = Path.Combine(Path.GetTempPath(), "knowledge_sources", jobId.ToString("N"));
            Directory.CreateDirectory(storageDir);
            var filePath = Path.Combine(storageDir, $"original{ext}");
            await using (var stream = new FileStream(filePath, FileMode.CreateNew))
                await file.CopyToAsync(stream, ct);

            // TODO: загрузка в MinIO, запись Job/Source в БД, публикация в ingestion.requested (outbox)
            return Accepted(new
            {
                job_id = jobId,
                source_id = sourceId,
                status = "queued",
                tenant_id = User.TenantId(),
                message = "Document accepted"
            });
        }

        [HttpPost("url")]
        public IActionResult IngestUrl([FromBody] UrlIngestRequest request)
        {
            if (!SsrfGuard.TryValidateUrl(request?.Url, out var uri, out var error))
                return BadRequest(new { error });

            // Фактическая загрузка выполняется воркером через HttpClient "safe-fetch"
            // (запрет редиректов и приватных адресов на уровне соединения).
            var jobId = Guid.NewGuid();
            return Accepted(new { job_id = jobId, status = "queued", url = uri!.GetLeftPart(UriPartial.Path) });
        }

        [HttpGet("jobs/{jobId:guid}")]
        public IActionResult GetJobStatus(Guid jobId)
        {
            // Статус хранится в БД (jobs) с фильтром по tenant_id; хранилище ещё не подключено.
            return StatusCode(StatusCodes.Status501NotImplemented, new { error = "Job store is not connected yet", job_id = jobId });
        }
    }

    public class UrlIngestRequest
    {
        public string Url { get; set; } = string.Empty;
    }
}
