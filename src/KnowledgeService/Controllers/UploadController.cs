using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using System.Data;

namespace KnowledgeService.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class UploadController : ControllerBase
    {
         


        [HttpPost]
        [Authorize]
        public async Task<IActionResult> UploadFileAsync(IFormFile file, CancellationToken ct)
        {
            if (!ModelState.IsValid) throw new Exception("Error"); 
            


            return Ok();
        }
    }
}
