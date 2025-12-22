using Amazon.Runtime;
using System.Net;

namespace S3BenchRunner.Mock;

/// <summary>
/// Factory for creating HTTP clients with mock HTTP message handlers.
/// This allows benchmarking without network I/O to isolate CPU/memory performance.
/// </summary>
public class MockHttpClientFactory : HttpClientFactory
{
    private readonly long _objectSize;
    private readonly long _partSize;

    public MockHttpClientFactory(long objectSize, long partSize)
    {
        _objectSize = objectSize;
        _partSize = partSize;
    }

    public override HttpClient CreateHttpClient(IClientConfig clientConfig)
    {
        var innerHandler = new HttpClientHandler();
        return new HttpClient(new MockHttpMessageHandler(innerHandler, _objectSize, _partSize));
    }
}

/// <summary>
/// Mock HTTP message handler that simulates S3 multipart download responses.
/// Returns mock data streams without making actual network calls.
/// </summary>
public class MockHttpMessageHandler : DelegatingHandler
{
    private readonly long _objectSize;
    private readonly long _partSize;
    private readonly long _partCount;

    public MockHttpMessageHandler(HttpMessageHandler innerHandler, long objectSize, long partSize) 
        : base(innerHandler)
    {
        _objectSize = objectSize;
        _partSize = partSize;
        _partCount = (long)Math.Ceiling((double)objectSize / partSize);
    }

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        // Check if this is a multipart download request (has partNumber query parameter)
        var uri = request.RequestUri;
        if (uri != null && uri.Query.Contains("partNumber="))
        {
            return Task.FromResult(CreateMultipartResponse(request));
        }

        // For non-multipart requests, return the full object
        return Task.FromResult(CreateFullObjectResponse());
    }

    private HttpResponseMessage CreateMultipartResponse(HttpRequestMessage request)
    {
        var partNumber = GetRequestPartNumber(request);
        
        // Calculate byte range for this part
        var start = (partNumber - 1) * _partSize;
        var end = Math.Min(start + _partSize - 1, _objectSize - 1);
        var partLength = end - start + 1;

        var response = new HttpResponseMessage(HttpStatusCode.PartialContent);
        response.Content = new StreamContent(new MockStream(partLength));
        response.Content.Headers.ContentLength = partLength;
        response.Content.Headers.TryAddWithoutValidation("Content-Range", $"bytes {start}-{end}/{_objectSize}");
        response.Headers.TryAddWithoutValidation("x-amz-mp-parts-count", _partCount.ToString());
        
        return response;
    }

    private HttpResponseMessage CreateFullObjectResponse()
    {
        var response = new HttpResponseMessage(HttpStatusCode.OK);
        response.Content = new StreamContent(new MockStream(_objectSize));
        response.Content.Headers.ContentLength = _objectSize;
        
        return response;
    }

    private int GetRequestPartNumber(HttpRequestMessage request)
    {
        var query = request.RequestUri!.Query;
        var queryParams = System.Web.HttpUtility.ParseQueryString(query);
        var partNumberStr = queryParams["partNumber"];
        
        if (int.TryParse(partNumberStr, out int partNumber))
        {
            return partNumber;
        }
        
        // Fallback: parse from query string manually
        var tokens = query.Split('=');
        if (tokens.Length >= 2)
        {
            return int.Parse(tokens[1].TrimEnd('&'));
        }
        
        return 1;
    }
}

/// <summary>
/// Mock stream that returns fake data without allocating actual buffers.
/// This minimizes memory overhead while still exercising the buffering logic.
/// </summary>
public class MockStream : Stream
{
    private readonly long _length;
    private long _position;
    private static readonly byte[] EmptyBuffer = new byte[8192]; // Reused across all instances

    public MockStream(long length)
    {
        _length = length;
    }

    public override bool CanRead => true;
    public override bool CanSeek => false;
    public override bool CanWrite => false;
    public override long Length => _length;
    
    public override long Position 
    { 
        get => _position; 
        set => throw new NotSupportedException("Seek is not supported."); 
    }

    public override int Read(byte[] buffer, int offset, int count)
    {
        if (_position >= _length)
        {
            return 0;
        }

        var bytesRemaining = _length - _position;
        var bytesToRead = (int)Math.Min(count, bytesRemaining);
        
        // Don't actually fill the buffer - just advance position
        // This is sufficient for benchmarking buffering logic
        _position += bytesToRead;
        
        return bytesToRead;
    }

    public override async Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken)
    {
        // For async reads, we can optionally add a tiny delay to simulate some I/O overhead
        // But for pure CPU/memory benchmarking, we skip the delay
        return Read(buffer, offset, count);
    }

    public override long Seek(long offset, SeekOrigin origin)
    {
        throw new NotSupportedException("Seek is not supported.");
    }

    public override void SetLength(long value)
    {
        throw new NotSupportedException();
    }

    public override void Write(byte[] buffer, int offset, int count)
    {
        throw new NotSupportedException();
    }

    public override void Flush()
    {
        // No-op
    }
}
